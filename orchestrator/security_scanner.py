import os
import re
import json
import subprocess
import shutil
import logging

logger = logging.getLogger("orchestrator.security_scanner")

class SecurityScanner:
    """
    Automates security checks on generated Terraform files.
    Integrates with Checkov CLI and falls back to rule-based validation.
    """

    def __init__(self, checkov_config_path=None):
        self.checkov_config_path = checkov_config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "security",
            "checkov.yaml"
        )

    def scan_directory(self, target_dir: str) -> dict:
        """
        Runs compliance scan on the target directory and returns findings.
        """
        logger.info(f"Initiating security scan on directory: {target_dir}")
        checkov_bin = shutil.which("checkov")

        if not checkov_bin:
            logger.info("Checkov CLI not found. Attempting to auto-install checkov via pip...")
            try:
                subprocess.run(["pip3", "install", "--upgrade", "checkov"], check=True, capture_output=True)
                checkov_bin = shutil.which("checkov")
                if checkov_bin:
                    logger.info("Checkov CLI successfully auto-installed.")
            except Exception as e:
                logger.warning(f"Failed to auto-install Checkov: {e}. Falling back to internal validation.")

        if checkov_bin:
            try:
                # Run Checkov against directory and output json
                cmd = [checkov_bin, "-d", target_dir, "--output", "json"]
                if os.path.exists(self.checkov_config_path):
                    cmd.extend(["--config-file", self.checkov_config_path])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Checkov returns non-zero code if checks fail, so we parse stdout
                if result.stdout.strip():
                    scan_data = json.loads(result.stdout)
                    
                    # Checkov output can be a list or a single object
                    if isinstance(scan_data, list):
                        # Filter out empty elements
                        scan_data = [item for item in scan_data if item]
                        if not scan_data:
                            return {"success": True, "findings": [], "score": "10/10"}
                        # Merge checks
                        failed_checks = []
                        passed = 0
                        for report in scan_data:
                            failed_checks.extend(report.get("results", {}).get("failed_checks", []))
                            passed += report.get("summary", {}).get("passed", 0)
                    else:
                        failed_checks = scan_data.get("results", {}).get("failed_checks", [])
                        passed = scan_data.get("summary", {}).get("passed", 0)

                    findings = []
                    for check in failed_checks:
                        findings.append({
                            "check_id": check.get("check_id"),
                            "check_name": check.get("check_name"),
                            "file_path": check.get("file_path"),
                            "severity": check.get("severity", "HIGH"),
                            "remediation": check.get("guideline", "Review resource configurations.")
                        })

                    success = len(findings) == 0
                    score = "10/10" if success else f"{passed}/{passed + len(findings)}"
                    
                    return {
                        "success": success,
                        "findings": findings,
                        "score": score,
                        "tool": "Checkov CLI"
                    }
            except Exception as e:
                logger.error(f"Failed to execute Checkov CLI: {e}. Falling back to internal rule validation.")

        # Fallback to internal rule-based regex checks
        return self._run_internal_checks(target_dir)

    def _run_internal_checks(self, target_dir: str) -> dict:
        logger.info("Executing internal rule-based regex validation")
        main_tf_path = os.path.join(target_dir, "main.tf")
        findings = []

        if not os.path.exists(main_tf_path):
            return {
                "success": False,
                "findings": [{"check_id": "ERR_NO_SOURCE", "check_name": "main.tf source file is missing", "severity": "CRITICAL"}],
                "score": "0/10",
                "tool": "Internal Validator"
            }

        with open(main_tf_path, "r") as f:
            content = f.read()

        # Check 1: Enforce IMDSv2 (metadata http_tokens required)
        if "metadata_options" in content:
            if not re.search(r'http_tokens\s*=\s*"required"', content):
                findings.append({
                    "check_id": "CKV_AWS_79",
                    "check_name": "Ensure EC2 metadata service requires IMDSv2",
                    "severity": "HIGH",
                    "remediation": "Set http_tokens = \"required\" inside metadata_options."
                })
        else:
            if "aws_instance" in content:
                findings.append({
                    "check_id": "CKV_AWS_79",
                    "check_name": "Ensure EC2 metadata service requires IMDSv2 (metadata_options missing)",
                    "severity": "HIGH",
                    "remediation": "Add metadata_options block with http_tokens = \"required\"."
                })

        # Check 2: EBS Volume Encryption
        if "root_block_device" in content:
            if not re.search(r'encrypted\s*=\s*true', content):
                findings.append({
                    "check_id": "CKV_AWS_135",
                    "check_name": "Ensure EBS volume is encrypted",
                    "severity": "HIGH",
                    "remediation": "Set encrypted = true in root_block_device."
                })

        # Check 3: S3 Public Access Blocking
        if "aws_s3_bucket" in content:
            if "aws_s3_bucket_public_access_block" not in content:
                findings.append({
                    "check_id": "CKV_AWS_19",
                    "check_name": "Ensure S3 bucket public access block is configured",
                    "severity": "HIGH",
                    "remediation": "Add aws_s3_bucket_public_access_block resource."
                })

        # Check 4: RDS Public Access
        if "aws_db_instance" in content:
            if not re.search(r'publicly_accessible\s*=\s*false', content):
                findings.append({
                    "check_id": "CKV_AWS_89",
                    "check_name": "Ensure RDS instance is not publicly accessible",
                    "severity": "CRITICAL",
                    "remediation": "Set publicly_accessible = false."
                })

        success = len(findings) == 0
        score = "10/10" if success else f"{10 - len(findings)}/10"

        return {
            "success": success,
            "findings": findings,
            "score": score,
            "tool": "Internal Validator"
        }

if __name__ == "__main__":
    scanner = SecurityScanner()
    # Test on a deployment
    res = scanner.scan_directory("/Users/nikhildhakad/data/tata1mg/deployments/INFRA-103")
    print(json.dumps(res, indent=2))
