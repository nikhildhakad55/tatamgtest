import json
import logging
import boto3

logger = logging.getLogger("orchestrator.request_parser")

class RequestParser:

    # AWS Region to AWS Pricing API Location name lookup map
    REGION_TO_LOCATION = {
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
        "ap-south-1": "Asia Pacific (Mumbai)",
        "eu-central-1": "Europe (Frankfurt)"
    }

    # Deterministic Target Deployment Routing Map
    ENVIRONMENT_MAP = {
        "dev": {
            "region": "us-west-2",
            "vpc_name": "dev-vpc"
        },
        "qa": {
            "region": "ap-south-1",
            "vpc_name": "qa-vpc"
        },
        "staging": {
            "region": "us-east-1",
            "vpc_name": "staging-vpc"
        },
        "prod": {
            "region": "eu-central-1",
            "vpc_name": "prod-vpc"
        }
    }

    def __init__(self, use_llm=True, bedrock_region="us-east-1"):
        self.use_llm = use_llm
        self.bedrock_region = bedrock_region

    def parse_request(self, user_prompt: str) -> dict:
        logger.info(f"Parsing user request: {user_prompt}")
        
        # Parse using Amazon Bedrock as the single source of truth
        parsed_args = self._parse_with_bedrock(user_prompt)

        # Apply Matrix Layer mappings
        resource_type = parsed_args.get("resource_type", "ec2_instance")
        environment = parsed_args.get("environment", "dev")
        vcpu = parsed_args.get("vcpu", 2)
        memory_gb = parsed_args.get("memory_gb", 4)
        
        # Lookup mapping info
        env_config = self.ENVIRONMENT_MAP.get(environment, {
            "region": "us-east-1",
            "vpc_name": f"{environment}-vpc"
        })
        region = env_config.get("region", "us-east-1")

        # Map vcpu/ram to an EC2 instance class
        instance_type = self._map_instance_type(vcpu, memory_gb, region)

        return {
            "resource_type": resource_type,
            "environment": environment,
            "specifications": {
                "vcpu": vcpu,
                "memory_gb": memory_gb,
                "instance_type": instance_type,
                "instance_options": self._get_instance_options(vcpu, memory_gb, region),
                "root_volume_size": 20,
                "root_volume_type": "gp3"
            },
            "networking": {
                "vpc_name": env_config["vpc_name"],
                "allowed_ingress_ports": parsed_args.get("allowed_ingress_ports", [443])
            },
            "bucket_specifications": {
                "bucket_name_prefix": parsed_args.get("bucket_name_prefix", "app-data")
            },
            "tags": {
                "Environment": environment.capitalize()
            }
        }

    def _parse_with_bedrock(self, user_prompt: str) -> dict:
        client = boto3.client("bedrock-runtime", region_name=self.bedrock_region)
        
        # Bedrock lightweight model for testing (Nova Micro)
        model_ids = [
            "us.amazon.nova-micro-v1:0",
            "amazon.nova-micro-v1:0"
        ]

        # Define structured schema tool
        tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": "parse_infrastructure_request",
                        "description": "Parses user infrastructure requests into structured JSON.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "resource_type": {"type": "string", "enum": ["ec2_instance", "s3_bucket", "rds_instance"]},
                                    "environment": {"type": "string", "enum": ["dev", "qa", "staging", "prod"]},
                                    "vcpu": {"type": "integer"},
                                    "memory_gb": {"type": "integer"},
                                    "allowed_ingress_ports": {"type": "array", "items": {"type": "integer"}},
                                    "bucket_name_prefix": {"type": "string"}
                                },
                                "required": ["resource_type", "environment"]
                            }
                        }
                    }
                }
            ],
            "toolChoice": {
                "tool": {
                    "name": "parse_infrastructure_request"
                }
            }
        }

        last_error = None
        for model_id in model_ids:
            try:
                response = client.converse(
                    modelId=model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"text": user_prompt}]
                        }
                    ],
                    toolConfig=tool_config
                )
                
                output_message = response['output']['message']
                for content in output_message.get('content', []):
                    if 'toolUse' in content:
                        tool_use = content['toolUse']
                        return tool_use['input']
            except Exception as e:
                last_error = e
                logger.info(f"Bedrock model {model_id} failed or not accessible: {e}")
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No active Bedrock model IDs succeeded.")



    def _get_instance_price(self, instance_type: str, region: str) -> float:
        try:
            # Pricing API endpoint is in us-east-1
            pricing = boto3.client("pricing", region_name="us-east-1")
            
            # Map region to Location name for Pricing API
            location = self.REGION_TO_LOCATION.get(region, "US East (N. Virginia)")
            
            response = pricing.get_products(
                ServiceCode="AmazonEC2",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                    {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                    {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                    {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                    {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"}
                ]
            )
            
            price_list = response.get("PriceList", [])
            if price_list:
                product = json.loads(price_list[0])
                terms = product.get("terms", {})
                on_demand = terms.get("OnDemand", {})
                for term_id in on_demand:
                    rate_code_details = on_demand[term_id].get("priceDimensions", {})
                    for dimension_id in rate_code_details:
                        price_per_unit = rate_code_details[dimension_id].get("pricePerUnit", {})
                        usd_rate = float(price_per_unit.get("USD", 0.0))
                        # Return monthly rate (hourly rate * 730 hours)
                        return usd_rate * 730.0
            raise ValueError(f"No pricing product found for {instance_type} in {location}")
        except Exception as e:
            logger.error(f"Failed to fetch live AWS price for {instance_type}: {e}")
            raise

    def _map_instance_type(self, vcpu: int, memory_gb: int, region: str) -> str:
        options = self._query_aws_instance_options(vcpu, memory_gb, region)
        if options:
            for opt in options:
                if opt.get("recommended"):
                    return opt["type"]
            return options[0]["type"]
        raise RuntimeError("No matching dynamic instance type options found.")

    def _get_instance_options(self, vcpu: int, memory_gb: int, region: str) -> list:
        """
        Dynamically returns list of option candidate instances (AMD)
        matching the requested vCPUs and memory_gb, querying AWS EC2 API.
        """
        options = self._query_aws_instance_options(vcpu, memory_gb, region)
        if options:
            return options
        raise RuntimeError("No matching dynamic instance type options found.")

    def _query_aws_instance_options(self, vcpu: int, memory_gb: int, region: str) -> list:
        ec2 = boto3.client("ec2", region_name=region)
        allowed_families = ["t3a", "m6a", "c6a"]
        families_wildcard = [f"{fam}.*" for fam in allowed_families]
        
        instance_types = []
        try:
            paginator = ec2.get_paginator("describe_instance_types")
            for page in paginator.paginate(Filters=[{"Name": "instance-type", "Values": families_wildcard}]):
                instance_types.extend(page.get("InstanceTypes", []))
        except Exception as e:
            logger.warning(f"AWS describe_instance_types API failed: {e}")
            return []
            
        categories = {
            "General Purpose (AMD burstable)": ["t3a"],
            "General Purpose (AMD dedicated)": ["m6a"],
            "Compute Optimized (AMD)": ["c6a"]
        }
        
        matching_by_category = {cat: [] for cat in categories}
        for it in instance_types:
            name = it["InstanceType"]
            vcpus = it["VCpuInfo"]["DefaultVCpus"]
            mem_mib = it["MemoryInfo"]["SizeInMiB"]
            
            if vcpus >= vcpu and mem_mib >= memory_gb * 1024:
                parts = name.split('.')
                if parts:
                    fam = parts[0]
                    if fam in allowed_families:
                        for cat, fam_list in categories.items():
                            if fam in fam_list:
                                matching_by_category[cat].append({
                                    "type": name,
                                    "vcpus": vcpus,
                                    "memory_mib": mem_mib
                                })
                                break
                            
        result = []
        for cat, list_opts in matching_by_category.items():
            if not list_opts:
                continue
            list_opts.sort(key=lambda x: (x["vcpus"], x["memory_mib"], x["type"]))
            best_opt = list_opts[0]
            
            # Fetch real-time price using AWS Pricing API
            cost_rate = self._get_instance_price(best_opt["type"], region)
            
            result.append({
                "type": best_opt["type"],
                "category": cat,
                "cost_rate": float(cost_rate),
                "recommended": False
            })
            
        if not result:
            return []
            
        # Sort result by cost_rate to recommend the cheapest matching option dynamically
        result.sort(key=lambda x: x["cost_rate"])
        result[0]["recommended"] = True
        
        return result

if __name__ == "__main__":
    parser = RequestParser()
    res = parser.parse_request("create a 4 core 8 gb ram in stag vpc with only port 443 exposed to public")
    print(json.dumps(res, indent=2))

