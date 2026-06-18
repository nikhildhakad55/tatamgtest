provider "aws" {
  region = "us-east-1"
}

resource "aws_kms_key" "ebs" {
  description             = "KMS key for EC2 EBS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = "staging"
    Project     = "internal-infra"
    Owner       = "devops-team"
    CostCenter  = "CC-DEFAULT"
    ManagedBy   = "terraform"
  }
}

resource "aws_security_group" "instance_sg" {
  name        = "staging-internal-infra-sg"
  description = "Security group for EC2 instance with restricted access"
  vpc_id      = "vpc-0a1b2c3d4e5f6g7h8"

  
  ingress {
    description      = "Restricted inbound traffic on port 443"
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
  

  egress {
    description = "Allow secure outbound web traffic"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = "staging"
    Project     = "internal-infra"
    Owner       = "devops-team"
    CostCenter  = "CC-DEFAULT"
    ManagedBy   = "terraform"
  }
}

resource "aws_instance" "app_instance" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.xlarge"

  subnet_id                   = "subnet-12345abcd"
  vpc_security_group_ids      = [aws_security_group.instance_sg.id]
  associate_public_ip_address = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    kms_key_id            = aws_kms_key.ebs.arn
    delete_on_termination = true
  }

  monitoring = true

  tags = {
    Name        = "staging-internal-infra-app"
    Environment = "staging"
    Project     = "internal-infra"
    Owner       = "devops-team"
    CostCenter  = "CC-DEFAULT"
    ManagedBy   = "terraform"
  }
}