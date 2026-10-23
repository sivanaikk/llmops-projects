variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai, closest to the Hyderabad team
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "cluster_name" {
  type    = string
  default = "ai-runtime-dev"
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "karpenter_version" {
  type    = string
  default = "1.0.6"
}

variable "gateway_db_instance_class" {
  type    = string
  default = "db.t4g.small"
}
