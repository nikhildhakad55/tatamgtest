# IaC Self-Service Platform

An automated Infrastructure as Code (IaC) self-service framework. This platform translates developers' natural language requests into security-hardened, cost-optimized AWS infrastructure with an integrated multi-step approval workflow via Jira.

---

## 📁 Project Structure

```
tata1mg/
├── templates/                 # Hardened Terraform Templates (Sprint 1)
│   ├── ec2/
│   │   └── main.tf
│   ├── s3/
│   │   └── main.tf
│   └── rds/
│       └── main.tf
├── orchestrator/              # Python Orchestration Backend (Sprint 2)
│   ├── parser.py              # NLP Parameter Extraction
│   ├── jira_client.py         # Jira Ticket Lifecycle Client
│   ├── main.py                # FastAPI Application & Orchestration Logic
│   └── db_jira.json           # Mock Ticket Database (Auto-created)
├── security/                  # Static Security Policies (Sprint 1)
│   └── checkov.yaml           # Checkov Scanner Configuration
├── flow.txt                   # Deep-dive flow explanation
└── README.md                  # This documentation file
```

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.8+ installed. 

Install the required dependencies:
```bash
pip install fastapi uvicorn pydantic
```

*(Optional)* Install Checkov if you'd like the system to perform live scans instead of using mock templates validation:
```bash
pip install checkov
```

### 2. Running the Orchestrator
Start the FastAPI orchestrator local server:
```bash
uvicorn orchestrator.main:app --reload --port 8000
```

---

## 🚦 Verification & Usage Flow

You can test the entire pipeline end-to-end using curl or any API client (e.g., Postman).

### Step 1: Submit a Provisioning Request
Simulate a developer requesting an EC2 instance in staging:

```bash
curl -X POST "http://localhost:8000/provision" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "create a 4 core 8 gb ram in stag vpc with only port 443 exposed to public",
       "requester": "john.doe",
       "project": "Booking-Service",
       "owner": "Backend-Team",
       "cost_center": "CC-901"
     }'
```

**Expected Response**:
```json
{
  "ticket_id": "INFRA-101",
  "resource_type": "ec2_instance",
  "environment": "staging",
  "security_score": "Approved",
  "estimated_cost": "$66.60/month",
  "pr_number": 401,
  "status": "In Review"
}
```

This request:
1. Parses parameters using `parser.py` (VPC mapping, instance type).
2. Generates the corresponding Terraform `main.tf` and `terraform.tfvars` inside `/deployments/INFRA-101/`.
3. Performs a security compliance scan against CIS rules in `security/checkov.yaml`.
4. Estimates monthly costs.
5. Registers the tickets, PR information, security reports, and billing updates on Jira.

---

### Step 2: Check Jira Ticket Status
Query the current ticket status, approvals state, and bot comments:
```bash
curl "http://localhost:8000/ticket/INFRA-101"
```

---

### Step 3: Approve and Execute Deployments
Simulate the security, cost, and architecture review sign-offs. 

*1. Security Approval:*
```bash
curl -X POST "http://localhost:8000/approve" \
     -H "Content-Type: application/json" \
     -d '{"ticket_id": "INFRA-101", "stage": "security", "status": "Approved"}'
```

*2. Cost Approval:*
```bash
curl -X POST "http://localhost:8000/approve" \
     -H "Content-Type: application/json" \
     -d '{"ticket_id": "INFRA-101", "stage": "cost", "status": "Approved"}'
```

*3. Architectural Approval:*
```bash
curl -X POST "http://localhost:8000/approve" \
     -H "Content-Type: application/json" \
     -d '{"ticket_id": "INFRA-101", "stage": "architecture", "status": "Approved"}'
```

**Final Response (after the last approval is submitted)**:
```json
{
  "ticket_id": "INFRA-101",
  "approvals": {
    "security": "Approved",
    "cost": "Approved",
    "architecture": "Approved"
  },
  "status": "Done"
}
```
At this point, the backend orchestrator triggers the deployment runner and executes the provisioning process.
