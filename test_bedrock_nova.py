import boto3
import sys

def test_nova_bedrock():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    model_ids = [
        "us.amazon.nova-micro-v1:0",
        "amazon.nova-micro-v1:0"
    ]
    
    print("Testing connection to Bedrock Amazon Nova Micro in us-east-1...")
    for model_id in model_ids:
        try:
            print(f"Trying profile ID: {model_id}...")
            response = client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": "Hello! Confirm connection by replying with 'NOVA_OK'."}]
                    }
                ],
                inferenceConfig={"temperature": 0.0, "maxTokens": 10}
            )
            reply = response['output']['message']['content'][0]['text']
            print(f"✓ Response from {model_id}: {reply.strip()}")
            print("=== BEDROCK NOVA SUCCESS ===")
            return True
        except Exception as e:
            print(f"✗ Profile {model_id} failed: {e}\n")
            
    return False

if __name__ == "__main__":
    success = test_nova_bedrock()
    sys.exit(0 if success else 1)
