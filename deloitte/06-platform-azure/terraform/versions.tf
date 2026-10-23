terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.8" }
  }
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "sttfstateaiplatform"
  #   container_name       = "tfstate"
  #   key                  = "ai-platform/dev.tfstate"
  # }
}

provider "azurerm" {
  features {}
}
