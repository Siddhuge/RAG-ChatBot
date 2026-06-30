output "resource_group_name" {
  description = "Resource group containing the cluster."
  value       = azurerm_resource_group.this.name
}

output "cluster_name" {
  description = "AKS cluster name."
  value       = azurerm_kubernetes_cluster.this.name
}

output "cluster_fqdn" {
  description = "API server FQDN."
  value       = azurerm_kubernetes_cluster.this.fqdn
}

output "node_resource_group" {
  description = "Auto-created MC_ resource group holding the node VMSS and load balancer."
  value       = azurerm_kubernetes_cluster.this.node_resource_group
}

output "get_credentials_command" {
  description = "Run this to configure kubectl for the new cluster."
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.this.name} --name ${azurerm_kubernetes_cluster.this.name} --overwrite-existing"
}

output "kube_config_raw" {
  description = "Raw kubeconfig for the cluster (sensitive)."
  value       = azurerm_kubernetes_cluster.this.kube_config_raw
  sensitive   = true
}
