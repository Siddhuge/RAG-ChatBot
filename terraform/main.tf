resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  dns_prefix          = var.dns_prefix
  kubernetes_version  = var.kubernetes_version

  # Free control-plane tier: no per-cluster management fee or SLA charge.
  sku_tier = var.sku_tier

  default_node_pool {
    name                 = "system"
    vm_size              = var.node_vm_size
    os_disk_size_gb      = var.os_disk_size_gb
    type                 = "VirtualMachineScaleSets"
    auto_scaling_enabled = true
    min_count            = var.node_min_count
    max_count            = var.node_max_count
    node_count           = var.node_count
  }

  identity {
    type = "SystemAssigned"
  }

  # Azure CNI overlay: pods get IPs from an overlay range, so we don't burn
  # VNet IPs (cheaper and simpler than classic Azure CNI).
  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    load_balancer_sku   = "standard"
  }

  tags = var.tags

  lifecycle {
    # The autoscaler owns node_count after creation — don't fight it on apply.
    ignore_changes = [default_node_pool[0].node_count]
  }
}
