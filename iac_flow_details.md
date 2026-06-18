# End-to-End Self-Service IaC Pipeline Flow

This document describes how a developer's natural language input is processed, validated, approved, and executed by the Infrastructure as Code (IaC) Self-Service Platform.

---

## 🗺️ Pipeline Diagram

```
[Developer Request]
        │ (Natural Language)
        ▼
┌───────────────────────────────┐
│ 1. Request Parsing (LLM)      │ ──► Extracts specs (CPU, RAM, ports)
└───────────────────────────────┘
        │ (Structured JSON)
        ▼
┌───────────────────────────────┐
│ 2. Ticketing & Tracking       │ ──► Creates Task ticket in Jira (e.g., KAN-101)
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 3. Terraform Code Gen         │ ──► Renders main.tf & terraform.tfvars
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 4. Security Scan (Checkov)    │ ──► Validates against CIS AWS Benchmarks
└───────────────────────────────┘
        │ (Security report)
        ▼
┌───────────────────────────────┐
│ 5. Cost Estimation (Infracost)│ ──► Runs AWS Pricing API comparison
└───────────────────────────────┘
        │ (Billing summary)
        ▼
┌───────────────────────────────┐
│ 6. Git Branch & Pull Request  │ ──► Opens PR with generated HCL code
└───────────────────────────────┘
        │ (Updates Jira Ticket)
        ▼
┌───────────────────────────────┐
│ 7. Multi-Gate Approvals       │ ──► Security, Cost, Arch review approvals
└───────────────────────────────┘
        │ (All Approved)
        ▼
┌───────────────────────────────┐
│ 8. GitOps Apply (Atlantis)    │ ──► Provisions resource on AWS Cloud
└───────────────────────────────┘
        │ (Apply Successful)
        ▼
┌───────────────────────────────┐
│ 9. Audit Trail Logging        │ ──► Logs deployment output & closes Jira ticket
└───────────────────────────────┘
```

---

## 🚦 Phase-by-Phase Flow Details

### Step 1: Input & Intent Parsing (NLP → JSON)
*   **Input**: The developer types a natural language request into a Slackbot, Teams, or Web UI:
    > *"Create a 4 core 8 gb ram in stag vpc with only port 443 exposed to public"*
*   **Processing**: An LLM (e.g., GPT-4o or Claude 3.5 Sonnet) parses this input using **JSON Schema Mode** to guarantee structured output:
    *   `4 core` ➔ `vcpu: 4`, mapped to instance type `t3.xlarge` or `m5.large`
    *   `8 gb ram` ➔ `memory_gb: 8`
    *   `stag vpc` ➔ `environment: staging`, looking up the corresponding AWS VPC configuration
    *   `port 443 exposed to public` ➔ Security Group rules allowing `0.0.0.0/0` on port `443`
*   **Output**: A clean parameters payload (JSON).

### Step 2: Jira Ticket Creation (Tracking & Audit)
*   **Action**: The orchestrator invokes the Jira Cloud REST API (using the `jira` client library).
*   **Details**:
    *   **Project**: `KAN` (Infra)
    *   **Work Type**: `Task`
    *   **Summary**: `Provision 4-core 8GB RAM instance in staging VPC`
    *   **Description**: Contains details of the request, requester's username, and a checklist of pending validation steps.
*   **Output**: Ticket key (e.g., `KAN-101`).

### Step 3: Terraform Code Generation
*   **Action**: The orchestrator selects the correct resource template folder (e.g., `templates/ec2/`) and:
    1. Copies the pre-hardened base template (`main.tf`) into a deployment directory (`deployments/KAN-101/`).
    2. Writes the parsed parameters into `terraform.tfvars`.
*   **Output**: Validated, deployable HCL configuration files.

### Step 4: Automated Security Scan (Security Gate)
*   **Tool Used**: **Checkov** (Static Application Security Testing / SAST tool for IaC).
*   **Checks run**: Scans the generated Terraform directory against **CIS AWS Foundations Benchmarks**.
*   **Scanning Flow**:
    *   If Checkov finds a failure (e.g., EBS volume encryption disabled, or IMDSv2 not enforced):
        1. It alerts the orchestrator.
        2. The orchestrator automatically adds security remediation blocks to the HCL code.
        3. A rescanning loop runs until Checkov returns `success: True`.
    *   The final compliance report is posted as a comment on the Jira ticket `KAN-101`.

### Step 5: Pre-Provisioning Cost Estimation (Cost Gate)
*   **Tool Used**: **Infracost** (AWS Pricing API integration).
*   **Checks run**: Compares the resource specifications in the HCL code with AWS pricing data.
*   **Billing Flow**:
    1. Runs `infracost breakdown --path deployments/KAN-101`.
    2. Calculates the exact monthly delta (e.g., `Total: $126.60/month`).
    3. Posts the cost breakdown to the Jira ticket comments.

### Step 6: Git Branch & Pull Request (Peer Review)
*   **Action**: The orchestrator uses the Git/GitHub API to:
    1. Create a Git branch: `feature/kan-101-ec2`.
    2. Commit the generated HCL files.
    3. Open a Pull Request (PR) in the infrastructure repository.
    4. Post the PR link to the Jira ticket.

### Step 7: Multi-Gate Approval Process
*   **Action**: Stakeholders review the details in Jira or the Git PR.
*   **Required Sign-offs**:
    *   **Security Approval**: Verifies Checkov results.
    *   **Cost Approval**: Finance review of Infracost monthly budget impact.
    *   **Architecture Review**: Code check.
*   **Approval**: Once all transitions are marked "Approved", the Jira ticket status automatically updates to "Approved".

### Step 8: Execution & Provisioning (GitOps Engine)
*   **Tool Used**: **Atlantis** or **GitHub Actions**.
*   **Deployment Flow**:
    1. Triggered by the approval webhook.
    2. Runs `terraform init` and `terraform apply` on AWS.
    3. Locks state file in S3/DynamoDB during deployment to prevent race conditions.

### Step 9: Audit Trail Logging
*   **Action**: The deployment log output is appended to the Jira ticket. The ticket is marked **Done**, and AWS CloudTrail captures all backend API requests for future compliance audits.

---

## 🛡️ Security Tools Used & Purpose

| Security Tool | Purpose in Pipeline | How it works |
| :--- | :--- | :--- |
| **Checkov** | Static Code Analysis (IaC SAST) | Scans the generated HCL files for security violations (like unencrypted volumes or wide-open ports) before any code is committed. |
| **tfsec** / **TFLint** | Linter & Style Validator | Ensures the generated Terraform code follows HCL syntax standards and code styles. |
| **AWS CloudTrail** | Audit Logging | Captures every API call made in the AWS account (who launched the instance, when, and how). |
| **AWS KMS** | Customer-Managed Encryption | Used in the Terraform templates to encrypt data-at-rest (EBS volumes, RDS databases, and S3 buckets). |
jinja2 also used by us to generate terraform code

---

## 📅 Step-by-Step Completion Plan

We will build the pipeline one step at a time:

* [x] **Step 1: Write Hardened Templates** (Complete - templates created for EC2, S3, RDS).
* [x] **Step 2: Base Parser & Ticketing** (Complete - parameter parsing and Jira connection verified).
* [ ] **Step 3: Integrated CLI Security Scanner** (Integrate actual Checkov execution script on the generated folders).
* [ ] **Step 4: Integrated Cost Estimator** (Connect Infracost CLI tool execution in backend).
* [ ] **Step 5: Git Integration** (Add Python code to commit to Git branch and open GitHub PR automatically).
* [ ] **Step 6: Webhook Approvals** (Build the transition listener for Jira approvals to trigger execution).
