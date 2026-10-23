output "aks_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "get_credentials" {
  value = "az aks get-credentials -g ${azurerm_resource_group.this.name} -n ${azurerm_kubernetes_cluster.this.name}"
}

output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "monitor_workspace_query_endpoint" {
  description = "Managed Prometheus endpoint for budgetgate --prometheus"
  value       = azurerm_monitor_workspace.this.query_endpoint
}

output "appinsights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}

output "openai_endpoint" {
  value = var.enable_azure_openai ? azurerm_cognitive_account.openai[0].endpoint : null
}
