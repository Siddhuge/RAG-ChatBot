# Terraform — Cost-Effective AKS Cluster

Provisions a small, autoscaling **Azure Kubernetes Service (AKS)** cluster to
run and test the RAG Chatbot. Designed to be cheap to run and easy to tear down.

## What it creates

| Resource | Notes |
|---|---|
| Resource group | `rag-chatbot-rg` (configurable) |
| AKS cluster | **Free** control-plane tier (no SLA fee) |
| Node pool | 1 node, autoscale 1→3, `Standard_B2ms` (2 vCPU / 8 GB burstable) |
| Networking | Azure CNI **overlay** + standard load balancer |
| Identity | System-assigned managed identity |

**No ACR** — the cluster pulls the public `siddhuge/rag-chatbot` image directly
from Docker Hub, so there's no container-registry cost.

## Cost notes (why this is cheap)

- **Free tier control plane** = $0 for cluster management.
- **B-series burstable** nodes are the cheapest general-purpose VMs.
- **Overlay networking** avoids consuming (and paying for) extra VNet IPs.
- You still pay for: node VM(s), OS disks, the standard load balancer, and
  egress — all minimal at this size.
- 💡 **Biggest saver while testing:** stop the cluster when idle. A stopped
  cluster bills almost nothing (only disks):
  ```bash
  az aks stop  --resource-group rag-chatbot-rg --name rag-chatbot-aks
  az aks start --resource-group rag-chatbot-rg --name rag-chatbot-aks
  ```
- When finished, `terraform destroy` removes everything.

## Prerequisites

```bash
az --version          # Azure CLI
terraform --version   # >= 1.5

az login                                   # authenticate
az account set --subscription "<sub-id>"   # pick the subscription
az account show --query id -o tsv          # copy this into terraform.tfvars
```

## Usage

```bash
cd terraform

# 1. Configure
cp terraform.tfvars.example terraform.tfvars
#   edit terraform.tfvars: set subscription_id (and tweak region/size if desired)

# 2. Initialize providers
terraform init

# 3. Preview
terraform plan

# 4. Create the cluster (~5-10 min)
terraform apply        # type 'yes' to confirm

# 5. Point kubectl at the new cluster (command is also a Terraform output)
az aks get-credentials --resource-group rag-chatbot-rg --name rag-chatbot-aks --overwrite-existing

# 6. Verify
kubectl get nodes
```

### Tear down

```bash
terraform destroy      # removes the cluster, node pool, and resource group
```

## Configuration

All inputs are in [`variables.tf`](variables.tf). Common overrides via
`terraform.tfvars`:

| Variable | Default | Why change it |
|---|---|---|
| `node_vm_size` | `Standard_B2ms` | `Standard_B2s` (4 GB) is cheaper but tight for the embedding model |
| `node_max_count` | `3` | Cap autoscaling |
| `location` | `eastus` | Region closest to you / cheapest |
| `sku_tier` | `Free` | `Standard` for an uptime SLA (costs more) |

## Remote state (optional, for CI/teams)

Local state is the default. To share state via Azure Storage, create the
backend once:

```bash
az group create -n tfstate-rg -l eastus
az storage account create -n tfstateXXXXXXXX -g tfstate-rg -l eastus --sku Standard_LRS
az storage container create -n tfstate --account-name tfstateXXXXXXXX
```

Then uncomment the backend block in [`backend.tf`](backend.tf) and run
`terraform init -migrate-state`.

## Next steps

This directory provisions the **cluster only**. Deploying the app onto it
(Kubernetes manifests/Helm for Qdrant + API + UI, secrets, ingress) and wiring
the GitHub Actions workflow to deploy on each push are the next phase.
