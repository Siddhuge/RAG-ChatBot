provider "azurerm" {
  features {}

  # azurerm v4 requires an explicit subscription id. Supply it via
  # terraform.tfvars, -var, or the TF_VAR_subscription_id / ARM_SUBSCRIPTION_ID
  # environment variable.
  subscription_id = var.subscription_id
}
