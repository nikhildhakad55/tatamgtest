import boto3
import json

def test():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    try:
        response = ec2.describe_instance_types(
            Filters=[
                {"Name": "vcpu-info.default-vcpus", "Values": ["2"]},
                {"Name": "memory-info.size-in-mib", "Values": ["4096"]}
            ]
        )
        print("Matches count:", len(response.get("InstanceTypes", [])))
        for it in response.get("InstanceTypes", [])[:5]:
            print(it["InstanceType"], it["VCpuInfo"]["DefaultVCpus"], it["MemoryInfo"]["SizeInMiB"])
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
