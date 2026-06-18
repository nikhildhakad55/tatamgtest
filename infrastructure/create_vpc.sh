#!/bin/bash
set -e

echo "🚀 Starting Staging VPC creation using AWS CLI..."

# Region setting
REGION="us-east-1"
CIDR_VPC="10.0.0.0/16"

# 1. Create VPC
echo "Creating VPC ($CIDR_VPC) in $REGION..."
VPC_ID=$(aws ec2 create-vpc \
    --cidr-block $CIDR_VPC \
    --region $REGION \
    --query 'Vpc.VpcId' \
    --output text)

echo "✅ Created VPC: $VPC_ID"

# Enable DNS support and hostnames
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support "{\"Value\":true}" --region $REGION
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames "{\"Value\":true}" --region $REGION

# Tag VPC
aws ec2 create-tags \
    --resources $VPC_ID \
    --tags Key=Name,Value=staging-vpc Key=Environment,Value=staging \
    --region $REGION

# 2. Create Public Subnets
echo "Creating Public Subnets..."
PUB_SUB1_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.1.0/24 \
    --availability-zone ${REGION}a \
    --region $REGION \
    --query 'Subnet.SubnetId' \
    --output text)
aws ec2 create-tags --resources $PUB_SUB1_ID --tags Key=Name,Value=staging-public-subnet-1 Key=Environment,Value=staging Key=Type,Value=public --region $REGION
echo "✅ Public Subnet 1: $PUB_SUB1_ID"

PUB_SUB2_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.2.0/24 \
    --availability-zone ${REGION}b \
    --region $REGION \
    --query 'Subnet.SubnetId' \
    --output text)
aws ec2 create-tags --resources $PUB_SUB2_ID --tags Key=Name,Value=staging-public-subnet-2 Key=Environment,Value=staging Key=Type,Value=public --region $REGION
echo "✅ Public Subnet 2: $PUB_SUB2_ID"

# Enable public IP assign on launch for public subnets
aws ec2 modify-subnet-attribute --subnet-id $PUB_SUB1_ID --map-public-ip-on-launch --region $REGION
aws ec2 modify-subnet-attribute --subnet-id $PUB_SUB2_ID --map-public-ip-on-launch --region $REGION

# 3. Create Private Subnets
echo "Creating Private Subnets..."
PRI_SUB1_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.10.0/24 \
    --availability-zone ${REGION}a \
    --region $REGION \
    --query 'Subnet.SubnetId' \
    --output text)
aws ec2 create-tags --resources $PRI_SUB1_ID --tags Key=Name,Value=staging-private-subnet-1 Key=Environment,Value=staging Key=Type,Value=private --region $REGION
echo "✅ Private Subnet 1: $PRI_SUB1_ID"

PRI_SUB2_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.11.0/24 \
    --availability-zone ${REGION}b \
    --region $REGION \
    --query 'Subnet.SubnetId' \
    --output text)
aws ec2 create-tags --resources $PRI_SUB2_ID --tags Key=Name,Value=staging-private-subnet-2 Key=Environment,Value=staging Key=Type,Value=private --region $REGION
echo "✅ Private Subnet 2: $PRI_SUB2_ID"

# 4. Internet Gateway (IGW)
echo "Creating and attaching Internet Gateway..."
IGW_ID=$(aws ec2 create-internet-gateway \
    --region $REGION \
    --query 'InternetGateway.InternetGatewayId' \
    --output text)
aws ec2 create-tags --resources $IGW_ID --tags Key=Name,Value=staging-igw Key=Environment,Value=staging --region $REGION
aws ec2 attach-internet-gateway --vpc-id $VPC_ID --internet-gateway-id $IGW_ID --region $REGION
echo "✅ Attached IGW: $IGW_ID"

# 5. Public Route Table
echo "Setting up routing..."
ROUTE_TABLE_ID=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --region $REGION \
    --query 'RouteTable.RouteTableId' \
    --output text)
aws ec2 create-tags --resources $ROUTE_TABLE_ID --tags Key=Name,Value=staging-public-rt Key=Environment,Value=staging --region $REGION

# Add route to Internet Gateway
aws ec2 create-route \
    --route-table-id $ROUTE_TABLE_ID \
    --destination-cidr-block 0.0.0.0/0 \
    --gateway-id $IGW_ID \
    --region $REGION

# Associate Route Table with Public Subnets
aws ec2 associate-route-table --subnet-id $PUB_SUB1_ID --route-table-id $ROUTE_TABLE_ID --region $REGION
aws ec2 associate-route-table --subnet-id $PUB_SUB2_ID --route-table-id $ROUTE_TABLE_ID --region $REGION
echo "✅ Set up Public Route Table: $ROUTE_TABLE_ID"

echo -e "\n🎉 Staging VPC creation completed successfully!"
echo "------------------------------------------------"
echo "VPC ID:          $VPC_ID"
echo "Public Subnet 1: $PUB_SUB1_ID"
echo "Public Subnet 2: $PUB_SUB2_ID"
echo "Private Subnet 1: $PRI_SUB1_ID"
echo "Private Subnet 2: $PRI_SUB2_ID"
echo "------------------------------------------------"
