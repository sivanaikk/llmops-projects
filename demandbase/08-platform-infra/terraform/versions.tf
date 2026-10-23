terraform {
  required_version = ">= 1.6"

  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.70" }
    helm   = { source = "hashicorp/helm", version = "~> 2.15" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }

  # Remote state: one state per environment, locked via DynamoDB.
  # backend "s3" {
  #   bucket         = "dbase-ai-runtime-tfstate"
  #   key            = "ai-runtime/dev/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "tf-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      project     = "ai-runtime"
      environment = var.environment
      owner       = "ai-runtime-services"
      cost-center = "ai-platform"
    }
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}
