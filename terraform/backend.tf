# State backend.
#
# By default Terraform stores state locally (terraform.tfstate). That's fine for
# a single person testing. For teams / CI, use a remote backend so state is
# shared and locked.
#
# To enable the Azure remote backend:
#   1. Create the storage account + container once (see terraform/README.md).
#   2. Uncomment the block below and fill in the names.
#   3. Run: terraform init -migrate-state
#
# terraform {
#   backend "azurerm" {
#     resource_group_name  = "tfstate-rg"
#     storage_account_name = "tfstateXXXXXXXX"   # globally unique, lowercase
#     container_name       = "tfstate"
#     key                  = "rag-chatbot-aks.tfstate"
#   }
# }
