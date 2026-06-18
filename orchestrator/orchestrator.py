import boto3
from jira import JIRA

# 1. Credentials
JIRA_SERVER = "https://infra360-team.atlassian.net"
JIRA_EMAIL = "nikhil.dhakad@infra360.io" 
import os
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Initialize Jira
jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))

# STEP 1: User Input
user_prompt = "create a 4 core 8 gb ram in stag vpc with only port 443 exposed to public"
print(f"1. Received prompt: '{user_prompt}'")

# STEP 2: Pre-Check Env
discovered_vpc_id = "vpc-0a1b2c3d" 

# STEP 3: Create Ticket via API using your exact form fields
print("2. Mapping properties to Jira Create Task Form fields automatically...")
issue_fields = {
    'project': {'key': 'KAN'},          # From your: Space* -> Infra (KAN)
    'issuetype': {'name': 'Task'},      # From your: Work type* -> Task
    'summary': 'Provision 4-core 8GB RAM instance in staging VPC',
    'description': f'Requirements parsed:\n- Prompt: {user_prompt}\n- Target Network: {discovered_vpc_id}\n\nRunning automated security policy scans...',
    'priority': {'name': 'Medium'}      # From your: Priority -> Medium
}

new_issue = jira.create_issue(fields=issue_fields)
print(f"🎉 Success! Automated ticket created: {new_issue.key}!")