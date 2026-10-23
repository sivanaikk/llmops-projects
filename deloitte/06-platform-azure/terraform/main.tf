locals {
  name = "${var.prefix}-${var.environment}"
  tags = { project = "applied-ai-sre-lab", environment = var.environment, owner = "sre" }
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

# ---------------- observability: Azure Monitor ----------------
resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.name}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = var.environment == "prod" ? -1 : 2 # cap log spend in dev
  tags                = local.tags
}

# Managed Prometheus: the same PromQL rules/SLOs as the lab run here.
resource "azurerm_monitor_workspace" "this" {
  name                = "amw-${local.name}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_application_insights" "this" {
  name                = "appi-${local.name}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "other" # OpenTelemetry traces from the agent land here
  tags                = local.tags
}

# ---------------- registry + secrets ----------------
resource "azurerm_container_registry" "this" {
  name                = replace("acr${local.name}", "-", "")
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "Standard"
  admin_enabled       = false
  tags                = local.tags
}

resource "azurerm_key_vault" "this" {
  name                       = "kv-${local.name}"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = var.environment == "prod"
  soft_delete_retention_days = 7
  tags                       = local.tags
}
