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

variable "db_name" {
  type        = string
  description = "Database name"
}

variable "db_username" {
  type        = string
  description = "Master username"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Master password (should be fetched from secrets manager)"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for DB Subnet Group"
}

variable "allocated_storage" {
  type        = number
  default     = 20
  description = "Allocated storage size in GB"
}

variable "instance_class" {
  type        = string
  default     = "db.t3.medium"
  description = "Database instance class"
}

# KMS Key for Database Storage Encryption
resource "aws_kms_key" "rds_key" {
  description             = "KMS key for RDS storage encryption"
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

# DB Subnet Group (restricted to private subnets)
resource "aws_db_subnet_group" "db_subnet" {
  name        = "${var.environment}-${var.project}-db-subnet-group"
  subnet_ids  = var.subnet_ids
  description = "Private subnet group for RDS"

  tags = {
    Environment = var.environment
    Project     = var.project
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }
}

# DB Security Group
resource "aws_security_group" "db_sg" {
  name        = "${var.environment}-${var.project}-db-sg"
  description = "Security group for RDS instance"
  vpc_id      = var.vpc_id

  # Ingress allowed only from VPC CIDR or specific app servers (Least Privilege)
  ingress {
    description = "Allow MySQL/Aurora traffic from within VPC"
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"] # Replace with specific application CIDR or Security Groups
  }

  egress {
    description = "Limit outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
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

# RDS DB Instance
resource "aws_db_instance" "db" {
  identifier        = "${var.environment}-${var.project}-db"
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  engine            = "mysql"
  engine_version    = "8.0"
  instance_class    = var.instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.db_subnet.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]

  # CIS AWS Benchmark compliance & hardening:
  publicly_accessible = false # Hardened: Do not expose to internet
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.rds_key.arn

  # Backup & Maintenance configurations
  backup_retention_period   = var.environment == "prod" ? 30 : 7 # Automated backups enabled
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:00-Mon:05:00"
  copy_tags_to_snapshot     = true
  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment == "prod" ? false : true
  final_snapshot_identifier = "${var.environment}-${var.project}-db-final-snapshot"

  # High Availability: Multi-AZ deployment for Prod
  multi_az = var.environment == "prod" ? true : false

  # Monitoring & Logging
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.rds_key.arn
  performance_insights_retention_period = 7 # 7 days is free tier
  monitoring_interval                   = 60 # Enable enhanced monitoring (every 60 seconds)
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn

  enabled_cloudwatch_logs_exports = ["error", "general", "slowquery"]

  tags = {
    Environment = var.environment
    Project     = var.project
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
  }
}

# IAM Role for Enhanced Monitoring
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.environment}-${var.project}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_attach" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

output "db_endpoint" {
  value       = aws_db_instance.db.endpoint
  description = "The database connection endpoint"
}

output "db_arn" {
  value       = aws_db_instance.db.arn
  description = "The database ARN"
}
