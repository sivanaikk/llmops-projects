# Gateway state: Postgres for LiteLLM keys/teams/spend, Redis for shared
# rate-limit counters, cooldowns and the response cache.

resource "random_password" "gateway_db" {
  length  = 32
  special = false
}

module "gateway_db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.9"

  identifier           = "${var.cluster_name}-litellm"
  engine               = "postgres"
  engine_version       = "16"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = var.gateway_db_instance_class
  allocated_storage    = 20

  db_name                     = "litellm"
  username                    = "litellm"
  password                    = random_password.gateway_db.result
  manage_master_user_password = false

  multi_az               = var.environment == "prod"
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.data_stores.id]

  backup_retention_period = 7
  deletion_protection     = var.environment == "prod"
  skip_final_snapshot     = var.environment != "prod"
}

resource "aws_elasticache_subnet_group" "gateway" {
  name       = "${var.cluster_name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "gateway" {
  replication_group_id       = "${var.cluster_name}-redis"
  description                = "LiteLLM rate limits, cooldowns and response cache"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = var.environment == "prod" ? 2 : 1
  automatic_failover_enabled = var.environment == "prod"
  subnet_group_name          = aws_elasticache_subnet_group.gateway.name
  security_group_ids         = [aws_security_group.data_stores.id]
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
}

resource "aws_security_group" "data_stores" {
  name   = "${var.cluster_name}-data-stores"
  vpc_id = module.vpc.vpc_id

  ingress {
    description     = "Postgres from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  ingress {
    description     = "Redis from EKS nodes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Secrets land in Secrets Manager; External Secrets Operator syncs them into
# the ai-runtime namespace (gitops/apps/base/ai-runtime/external-secret.yaml).
resource "aws_secretsmanager_secret" "gateway" {
  name = "${var.cluster_name}/litellm"
}

resource "random_password" "litellm_master_key" {
  length  = 40
  special = false
}

resource "aws_secretsmanager_secret_version" "gateway" {
  secret_id = aws_secretsmanager_secret.gateway.id
  secret_string = jsonencode({
    LITELLM_MASTER_KEY = "sk-${random_password.litellm_master_key.result}"
    DATABASE_URL       = "postgresql://litellm:${random_password.gateway_db.result}@${module.gateway_db.db_instance_endpoint}/litellm"
    REDIS_HOST         = aws_elasticache_replication_group.gateway.primary_endpoint_address
  })
}
