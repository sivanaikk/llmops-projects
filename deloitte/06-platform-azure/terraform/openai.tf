# Optional hosted model. Callers reach it through the LLM gateway, never directly,
# so swapping between the small open model and Azure OpenAI is a gateway config change.
resource "azurerm_cognitive_account" "openai" {
  count                         = var.enable_azure_openai ? 1 : 0
  name                          = "oai-${local.name}"
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "oai-${local.name}"
  local_auth_enabled            = false # Entra ID / workload identity only, no API keys
  public_network_access_enabled = var.environment != "prod"
  tags                          = local.tags
}

resource "azurerm_cognitive_deployment" "chat" {
  count                = var.enable_azure_openai ? 1 : 0
  name                 = var.openai_model
  cognitive_account_id = azurerm_cognitive_account.openai[0].id
  model {
    format  = "OpenAI"
    name    = var.openai_model
    version = var.openai_model_version
  }
  sku {
    name     = "Standard"
    capacity = 10 # thousands of tokens per minute: the provider quota the gateway must respect
  }
}
