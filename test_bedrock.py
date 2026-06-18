import boto3
import sys

def init_bedrock():
    print("=== AWS Bedrock Client Initialization ===")
    try:
        # Initializing Bedrock Runtime client targeting us-east-1 (AI Central Hub)
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        print("✓ Successfully created Bedrock Runtime client in us-east-1!")
        print(f"Client endpoint: {client.meta.endpoint_url}")
        
        # Check credentials active
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        print("✓ AWS credentials detected:")
        print(f"  Account: {identity.get('Account')}")
        print(f"  Arn: {identity.get('Arn')}")
        return True
    except Exception as e:
        print(f"✗ Failed to configure or connect AWS Bedrock client: {e}")
        return False

if __name__ == "__main__":
    success = init_bedrock()
    sys.exit(0 if success else 1)
