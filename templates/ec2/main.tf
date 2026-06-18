variable "environment" {
  type        = string
  description = "Target deployment environment (Dev/QA/Prod)"
}

variable "project" {
  type        = string
  description = "Project name"
}

variable "owner" {
  type        = string
  description = "Team or individual owner"
}

variable "cost_center" {
  type        = string
  description = "Cost center code for billing"
}

variable "instance_type" {
  type        = string
  default     = "t3.large"
  description = "EC2 Instance type"
}

variable "vpc_id" {
  type        = string
  description = "Target VPC ID"
}

variable "subnet_id" {
  type        = string
  description = "Target private subnet ID"
}

variable "allowed_ingress_ports" {
  type        = list(number)
  default     = [443]
  description = "List of allowed inbound ports"
}

# KMS Key for EBS encryption
resource "aws_kms_key" "ebs" {
  description             = "KMS key for EC2 EBS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Project     = var.project
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }
}

# Security Group
resource "aws_security_group" "instance_sg" {
  name        = "${var.environment}-${var.project}-sg"
  description = "Security group for EC2 instance with restricted access"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = var.allowed_ingress_ports
    content {
      description      = "Restricted inbound traffic on port ${ingress.value}"
      from_port        = ingress.value
      to_port          = ingress.value
      protocol         = "tcp"
      cidr_blocks      = ["0.0.0.0/0"] # Can be narrowed down based on requirements
      ipv6_cidr_blocks = ["::/0"]
    }
  }

  egress {
    description = "Allow secure outbound web traffic"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.environment
    Project     = var.project
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }
}

# EC2 Instance
resource "aws_instance" "app_instance" {
  ami           = "ami-0c55b159cbfafe1f0" # Resolved Amazon Linux 2 AMI
  instance_type = var.instance_type

  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.instance_sg.id]
  associate_public_ip_address = false # Hardened: No public IP

  # CIS AWS Benchmark: Enforce IMDSv2
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  # CIS AWS Benchmark: Root volume encryption via KMS key
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    kms_key_id            = aws_kms_key.ebs.arn
    delete_on_termination = true
  }

  # CloudWatch detailed monitoring
  monitoring = true

  tags = {
    Name        = "${var.environment}-${var.project}-app"
    Environment = var.environment
    Project     = var.project
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }
}

output "instance_id" {
  value       = aws_instance.app_instance.id
  description = "The ID of the EC2 instance"
}

output "security_group_id" {
  value       = aws_security_group.instance_sg.id
  description = "The ID of the Security Group"
}
