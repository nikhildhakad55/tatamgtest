import sys
import os
import json
import boto3

# Add orchestrator to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from request_parser import RequestParser
from main import get_environment_region, lookup_aws_network

def test_layer1():
    print("=== TESTING LAYER 1: INTENT & PARSING (LOCAL) ===")
    
    # 1. Developer Input Prompt
    prompt = "create a 4 core 8 gb ram in stag vpc with only port 443 exposed to public"
    print(f"\n[Input Prompt]: '{prompt}'")
    
    # 2. Extract specifications (Maps core/ram to instance type, extracts env)
    parser = RequestParser()
    parsed_specs = parser.parse_request(prompt)
    print("\n[Parsed Specifications]:")
    print(json.dumps(parsed_specs, indent=2))
    
    # 3. Look up environment config mapping (environments.json)
    env_name = parsed_specs["environment"].lower()
    region = get_environment_region(env_name)
    print(f"\n[Environment config lookup]: environment='{env_name}' maps to region='{region}'")
    
    # 4. Use boto3 to dynamically lookup/pre-verify AWS network IDs
    print("\n[Querying AWS via boto3 for VPC & private subnets]...")
    try:
        vpc_id, subnet_id, subnet_ids = lookup_aws_network(env_name, region)
        print("\n=== LAYER 1 SUCCESS ===")
        print(f"VPC ID Discovered:         {vpc_id}")
        print(f"Primary Private Subnet:    {subnet_id}")
        print(f"All Discovered Subnets:    {subnet_ids}")
    except Exception as e:
        print("\n=== LAYER 1 FAILED ===")
        print(f"Error during boto3 lookup: {e}")

if __name__ == "__main__":
    test_layer1()
