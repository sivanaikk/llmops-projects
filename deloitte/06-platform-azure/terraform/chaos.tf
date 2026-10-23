# Azure Chaos Studio: the cloud version of the Toxiproxy experiments in 05-resilience.
# Chaos Mesh on AKS kills agent pods; the hypothesis (checked by the same probes)
# is that PDB + replicas + retries keep the availability SLO.
resource "azurerm_chaos_studio_target" "aks" {
  location           = azurerm_resource_group.this.location
  target_resource_id = azurerm_kubernetes_cluster.this.id
  target_type        = "Microsoft-AzureKubernetesServiceChaosMesh"
}

resource "azurerm_chaos_studio_capability" "pod_chaos" {
  chaos_studio_target_id = azurerm_chaos_studio_target.aks.id
  capability_type        = "PodChaos-2.1"
}

resource "azurerm_chaos_studio_capability" "network_chaos" {
  chaos_studio_target_id = azurerm_chaos_studio_target.aks.id
  capability_type        = "NetworkChaos-2.1"
}

resource "azurerm_chaos_studio_experiment" "agent_pod_kill" {
  name                = "exp-${local.name}-agent-pod-kill"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name

  identity {
    type = "SystemAssigned"
  }

  selectors {
    name                    = "aks"
    chaos_studio_target_ids = [azurerm_chaos_studio_target.aks.id]
  }

  steps {
    name = "kill-agent-pods"
    branch {
      name = "pod-failure"
      actions {
        action_type   = "continuous"
        duration      = "PT10M"
        selector_name = "aks"
        urn           = azurerm_chaos_studio_capability.pod_chaos.urn
        parameters = {
          jsonSpec = jsonencode({
            action   = "pod-kill"
            mode     = "one"
            selector = { namespaces = ["agent-runtime"], labelSelectors = { "app.kubernetes.io/name" = "agent-runtime" } }
          })
        }
      }
    }
  }

  steps {
    name = "model-latency"
    branch {
      name = "network-delay"
      actions {
        action_type   = "continuous"
        duration      = "PT10M"
        selector_name = "aks"
        urn           = azurerm_chaos_studio_capability.network_chaos.urn
        parameters = {
          jsonSpec = jsonencode({
            action   = "delay"
            mode     = "all"
            selector = { namespaces = ["agent-runtime"], labelSelectors = { "app.kubernetes.io/name" = "ollama" } }
            delay    = { latency = "3000ms", jitter = "500ms", correlation = "0" }
          })
        }
      }
    }
  }
}

# Only the SRE group may start experiments (segregation of duties: product
# engineers can read results but not inject faults into shared environments).
resource "azurerm_role_assignment" "chaos_operators" {
  scope                = azurerm_chaos_studio_experiment.agent_pod_kill.id
  role_definition_name = "Contributor"
  principal_id         = var.sre_group_object_id
}

resource "azurerm_role_assignment" "experiment_on_aks" {
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service Cluster Admin Role"
  principal_id         = azurerm_chaos_studio_experiment.agent_pod_kill.identity[0].principal_id
}
