resource "azurerm_kubernetes_cluster" "this" {
  name                      = "aks-${local.name}"
  location                  = azurerm_resource_group.this.location
  resource_group_name       = azurerm_resource_group.this.name
  dns_prefix                = local.name
  kubernetes_version        = var.kubernetes_version
  sku_tier                  = var.environment == "prod" ? "Standard" : "Free"
  oidc_issuer_enabled       = true
  workload_identity_enabled = true # pods get Azure identities without secrets
  azure_policy_enabled      = true # admission policies: no privileged pods, approved registries
  local_account_disabled    = true

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.current.tenant_id
  }

  default_node_pool {
    name                         = "system"
    vm_size                      = "Standard_D2ds_v5"
    auto_scaling_enabled         = true
    min_count                    = 1
    max_count                    = 3
    only_critical_addons_enabled = true
    zones                        = ["1", "2", "3"]
    upgrade_settings {
      max_surge = "33%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "cilium" # the chart's NetworkPolicy restricts agent egress
    network_data_plane  = "cilium"
  }

  oms_agent {
    log_analytics_workspace_id      = azurerm_log_analytics_workspace.this.id
    msi_auth_for_monitoring_enabled = true
  }

  monitor_metrics {} # managed Prometheus scraping

  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }

  automatic_upgrade_channel = "patch"
  node_os_upgrade_channel   = "NodeImage"
  maintenance_window_auto_upgrade {
    frequency   = "Weekly"
    interval    = 1
    duration    = 4
    day_of_week = "Sunday"
    start_time  = "02:00"
  }

  tags = local.tags
}

# CPU pool for the agent and the small models (qwen2.5 0.5B/1.5B). Spot keeps
# dev cheap; the agent tolerates node loss because model calls are retried.
resource "azurerm_kubernetes_cluster_node_pool" "workload" {
  name                  = "workload"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = "Standard_D8ds_v5"
  auto_scaling_enabled  = true
  min_count             = 1
  max_count             = 6
  zones                 = ["1", "2", "3"]
  priority              = var.environment == "prod" ? "Regular" : "Spot"
  eviction_policy       = var.environment == "prod" ? null : "Delete"
  spot_max_price        = var.environment == "prod" ? null : -1
  node_labels           = { workload = "ai" }
  tags                  = local.tags
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                            = azurerm_container_registry.this.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}
