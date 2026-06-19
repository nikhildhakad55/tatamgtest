import os
import json
import logging
from datetime import datetime
from jira import JIRA

logger = logging.getLogger("orchestrator.jira_client")

TICKET_DB_PATH = os.path.join(os.path.dirname(__file__), "db_jira.json")

class JiraClient:
    """
    Jira Client that connects to the real Jira Cloud API and falls back
    gracefully to a local JSON database (db_jira.json) if credentials fail.
    """

    def __init__(self, domain=None, username=None, token=None):
        self.domain = domain or "https://infra360-team.atlassian.net"
        self.username = username or "nikhil.dhakad@infra360.io"
        self.token = token or os.getenv("JIRA_API_TOKEN")
        self._init_db()
        self.jira_conn = None
        self.use_real_jira = False
        
        try:
            self.jira_conn = JIRA(server=self.domain, basic_auth=(self.username, self.token))
            # Test connection
            self.jira_conn.projects()
            self.use_real_jira = True
            logger.info("Successfully connected to Jira Cloud API!")
        except Exception as e:
            logger.warning(f"Failed to connect to real Jira Cloud: {e}. Falling back to mock local DB.")

    def _init_db(self):
        if not os.path.exists(TICKET_DB_PATH):
            with open(TICKET_DB_PATH, "w") as f:
                json.dump({"tickets": {}, "next_id": 101}, f)

    def _read_db(self):
        with open(TICKET_DB_PATH, "r") as f:
            return json.load(f)

    def _write_db(self, data):
        with open(TICKET_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def create_ticket(self, summary: str, description: str, requester: str, specs: dict = None) -> str:
        """
        Creates an infrastructure request ticket (e.g. KAN-12 or INFRA-101)
        """
        ticket_id = None
        
        # 1. Try to create in real JIRA
        if self.use_real_jira:
            try:
                issue_fields = {
                    'project': {'key': 'KAN'},
                    'issuetype': {'name': 'Task'},
                    'summary': summary,
                    'description': description,
                    'priority': {'name': 'Medium'}
                }
                issue = self.jira_conn.create_issue(fields=issue_fields)
                ticket_id = issue.key
                logger.info(f"Created real Jira issue: {ticket_id}")
            except Exception as e:
                logger.error(f"Failed to create real Jira issue: {e}. Falling back to mock ID.")

        # 2. Local database backup creation & synchronization
        db = self._read_db()
        if not ticket_id:
            ticket_id = f"INFRA-{db['next_id']}"
            db["next_id"] += 1

        db["tickets"][ticket_id] = {
            "key": ticket_id,
            "summary": summary,
            "description": description,
            "status": "To Do",
            "requester": requester,
            "specs": specs,
            "comments": [],
            "approvals": {
                "security": "Pending",
                "cost": "Pending",
                "architecture": "Pending"
            },
            "created_at": datetime.now().isoformat()
        }
        
        self._write_db(db)
        logger.info(f"Jira Ticket cached locally: {ticket_id}")
        return ticket_id

    def get_ticket(self, ticket_id: str) -> dict:
        db = self._read_db()
        
        # Sync status from real JIRA if available
        if self.use_real_jira and ticket_id.startswith("KAN-"):
            try:
                issue = self.jira_conn.issue(ticket_id)
                status_name = issue.fields.status.name
                if ticket_id in db["tickets"]:
                    db["tickets"][ticket_id]["status"] = status_name
                    self._write_db(db)
            except Exception as e:
                logger.warning(f"Could not refresh issue status from real Jira: {e}")
                
        return db["tickets"].get(ticket_id)

    def get_all_tickets(self) -> list:
        db = self._read_db()
        return list(db["tickets"].values())

    def add_comment(self, ticket_id: str, author: str, body: str):
        """
        Adds a comment to a Jira ticket (e.g. security report, cost estimates)
        """
        db = self._read_db()
        comment_added = False
        
        # 1. Add comment to real Jira
        if self.use_real_jira and ticket_id.startswith("KAN-"):
            try:
                formatted_body = f"*{author}*:\n{body}"
                self.jira_conn.add_comment(ticket_id, formatted_body)
                comment_added = True
                logger.info(f"Added comment to real Jira ticket: {ticket_id}")
            except Exception as e:
                logger.error(f"Failed to comment on real Jira ticket: {e}")

        # 2. Add to local db cache
        if ticket_id in db["tickets"]:
            db["tickets"][ticket_id]["comments"].append({
                "author": author,
                "body": body,
                "timestamp": datetime.now().isoformat()
            })
            self._write_db(db)
            logger.info(f"Added comment locally to cached ticket {ticket_id} by {author}")
            return True
            
        return comment_added

    def update_ticket_specs(self, ticket_id: str, specs: dict) -> bool:
        """
        Updates the specifications payload (e.g. dynamic option pricing) for a cached ticket.
        """
        db = self._read_db()
        if ticket_id in db["tickets"]:
            db["tickets"][ticket_id]["specs"] = specs
            self._write_db(db)
            logger.info(f"Updated specs for ticket {ticket_id} in local cache")
            return True
        return False

    def update_approval(self, ticket_id: str, stage: str, status: str) -> bool:
        """
        Updates approval stages: security, cost, or architecture.
        If all are approved, it transitions the issue status.
        """
        db = self._read_db()
        if ticket_id in db["tickets"]:
            ticket = db["tickets"][ticket_id]
            if stage in ticket["approvals"]:
                ticket["approvals"][stage] = status
                
                # Check if all stages are approved
                approvals = ticket["approvals"]
                if all(v == "Approved" for v in approvals.values()):
                    ticket["status"] = "Approved"
                    # Transition real Jira ticket to Executing/In Progress
                    self.transition_status(ticket_id, "In Progress")
                    
                self._write_db(db)
                logger.info(f"Updated {stage} approval to {status} for {ticket_id}")
                return True
        return False

    def transition_status(self, ticket_id: str, new_status: str) -> bool:
        db = self._read_db()
        transitioned = False
        
        # 1. Transition real JIRA issue status
        if self.use_real_jira and ticket_id.startswith("KAN-"):
            try:
                # Transition IDs: 21 = In Progress, 31 = Done
                transition_id = None
                if new_status.lower() in ["in progress", "executing", "in review"]:
                    transition_id = "21"
                elif new_status.lower() in ["done", "completed"]:
                    transition_id = "31"
                elif new_status.lower() in ["to do", "todo"]:
                    transition_id = "11"
                    
                if transition_id:
                    self.jira_conn.transition_issue(ticket_id, transition_id)
                    transitioned = True
                    logger.info(f"Transitioned real Jira issue {ticket_id} using ID {transition_id} ({new_status})")
            except Exception as e:
                logger.error(f"Failed to transition real Jira issue {ticket_id}: {e}")

        # 2. Update local db cache
        if ticket_id in db["tickets"]:
            db["tickets"][ticket_id]["status"] = new_status
            self._write_db(db)
            logger.info(f"Transitioned cached ticket {ticket_id} to status {new_status}")
            return True
            
        return transitioned

