#!/bin/bash

# Setup and Test Bedrock Access Script
# This script helps configure AWS CLI credentials and tests connection to Claude 3.5 Sonnet on AWS Bedrock.

echo "======================================================"
echo " AWS Bedrock & Claude 3.5 Sonnet Configuration Helper"
echo "======================================================"

# 1. Check AWS CLI configuration
echo -e "\n[Step 1] Checking AWS CLI Configuration..."
if aws sts get-caller-identity &> /dev/null; then
    echo "✓ AWS Credentials verified successfully."
    aws sts get-caller-identity --query "{Account:Account,Arn:Arn}" --output table
else
    echo "✗ No valid AWS credentials found or access is invalid."
    echo "Please configure your AWS Access Key, Secret Key, and Region now."
    aws configure
fi

# 2. Check Bedrock service availability in the chosen region
REGION=$(aws configure get region)
if [ -z "$REGION" ]; then
    REGION="us-east-1"
fi
echo -e "\n[Step 2] Checking Bedrock service in region: $REGION..."
if aws bedrock list-foundation-models --region "$REGION" --query "modelSummaries[?contains(modelId, 'claude-3-5')].modelId" --output table 2>/dev/null; then
    echo "✓ Bedrock service is accessible."
else
    echo "⚠️  Could not query Bedrock models. This could mean your credentials lack 'bedrock:ListFoundationModels' permission or the region lacks Bedrock support."
fi

# 3. Create a test python script to run a mock Bedrock Converse call
echo -e "\n[Step 3] Creating Bedrock Python test client..."
cat << 'EOF' > test_bedrock_connection.py
import boto3
import json
import sys

def test_nova_bedrock():
    region = boto3.Session().region_name or "us-east-1"
    print(f"Initializing Bedrock runtime client in region: {region}...")
    client = boto3.client("bedrock-runtime", region_name=region)
    
    # We will try Amazon Nova Micro model and its US inference profile
    model_ids = [
        "us.amazon.nova-micro-v1:0",
        "amazon.nova-micro-v1:0"
    ]
    
    success = False
    for model_id in model_ids:
        print(f"Testing model: {model_id}...")
        try:
            response = client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": "Hello! Confirm connection by replying with 'SUCCESS'"}]
                    }
                ],
                inferenceConfig={"temperature": 0.0, "maxTokens": 10}
            )
            reply = response['output']['message']['content'][0]['text']
            print(f"✓ Success! Reply from {model_id}: {reply.strip()}")
            success = True
            break
        except Exception as e:
            print(f"✗ Failed testing {model_id}: {e}\n")
            
    if success:
        print("=== BEDROCK INITIALIZATION SUCCESSFUL ===")
        sys.exit(0)
    else:
        print("=== BEDROCK INITIALIZATION FAILED ===")
        print("Note: If you get AccessDeniedException, please make sure you requested model access for Amazon Nova Micro in your AWS Console under Bedrock -> Model Access.")
        sys.exit(1)

if __name__ == "__main__":
    test_nova_bedrock()
EOF

# 4. Run Python test
echo -e "\n[Step 4] Running Python connection test..."
python3 test_bedrock_connection.py
TEST_STATUS=$?

# Cleanup temporary python test file
rm -f test_bedrock_connection.py

if [ $TEST_STATUS -eq 0 ]; then
    echo -e "\nAll checks passed! Your AWS Bedrock connection is ready."
else
    echo -e "\nBedrock connection test failed. Follow instructions above to configure access."
fi
