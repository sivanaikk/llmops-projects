variable "location" {
  type    = string
  default = "centralindia"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "prefix" {
  type    = string
  default = "aiplat"
}

variable "kubernetes_version" {
  type    = string
  default = "1.30"
}

variable "enable_azure_openai" {
  description = "Create an Azure OpenAI account + small model deployment. Off by default: the lab runs small open models on AKS."
  type        = bool
  default     = false
}

variable "openai_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "openai_model_version" {
  type    = string
  default = "2024-07-18"
}

variable "sre_group_object_id" {
  description = "Entra ID group allowed to run chaos experiments and approve prod (segregation of duties)."
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}
