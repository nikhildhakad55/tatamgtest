import boto3
import json

def test():
    try:
        # Pricing API endpoint is in us-east-1
        pricing = boto3.client("pricing", region_name="us-east-1")
        
        response = pricing.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": "t3.xlarge"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"}
            ]
        )
        price_list = response.get("PriceList", [])
        print("Matches found:", len(price_list))
        if price_list:
            product = json.loads(price_list[0])
            terms = product.get("terms", {})
            on_demand = terms.get("OnDemand", {})
            for term_id in on_demand:
                rate_code_details = on_demand[term_id].get("priceDimensions", {})
                for dimension_id in rate_code_details:
                    price_per_unit = rate_code_details[dimension_id].get("pricePerUnit", {})
                    usd_rate = float(price_per_unit.get("USD", 0.0))
                    print("Hourly Rate USD:", usd_rate)
                    print("Monthly Rate USD:", usd_rate * 730)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
