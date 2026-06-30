variable "subscription_id" {
  type        = string
  description = "Azure subscription ID to deploy into."
}

variable "location" {
  type        = string
  description = "Azure region."
  default     = "eastus"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group to create for the cluster."
  default     = "rag-chatbot-rg"
}

variable "cluster_name" {
  type        = string
  description = "AKS cluster name."
  default     = "rag-chatbot-aks"
}

variable "dns_prefix" {
  type        = string
  description = "DNS prefix for the cluster API server."
  default     = "ragchatbot"
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes version. null = AKS default (recommended)."
  default     = null
}

variable "sku_tier" {
  type        = string
  description = "Control-plane tier. 'Free' has no SLA charge (best for testing); 'Standard' adds an uptime SLA."
  default     = "Free"
}

# --- Node pool (cost-effective defaults) ---

variable "node_vm_size" {
  type        = string
  description = "VM size for the node pool. B-series burstable is cheapest. Standard_B2ms = 2 vCPU / 8 GB (headroom for the embedding model). Standard_B2s = 2 vCPU / 4 GB is cheaper but tight."
  default     = "Standard_B2ms"
}

variable "node_count" {
  type        = number
  description = "Initial node count (ignored on subsequent applies; autoscaler manages it)."
  default     = 1
}

variable "node_min_count" {
  type        = number
  description = "Autoscaler minimum nodes."
  default     = 1
}

variable "node_max_count" {
  type        = number
  description = "Autoscaler maximum nodes."
  default     = 3
}

variable "os_disk_size_gb" {
  type        = number
  description = "OS disk size per node (GB)."
  default     = 32
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default = {
    project = "rag-chatbot"
    env     = "test"
  }
}
