# Ingress + TLS — one-time cluster setup

The app manifests (`60-ingress.yaml`) assume an NGINX ingress controller and a
TLS secret exist in the cluster. These are **one-time cluster setup** (like the
cluster itself), not part of the per-deploy `kubectl apply -f k8s/`.

## 1. Install the NGINX ingress controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/cloud/deploy.yaml
kubectl -n ingress-nginx wait --for=condition=available deployment/ingress-nginx-controller --timeout=180s

# Get its public IP
kubectl -n ingress-nginx get svc ingress-nginx-controller
```

## 2. Pick a host

No domain needed for testing — use **nip.io**, which resolves `*.<IP>.nip.io`
to `<IP>`:

```
HOST=rag.<INGRESS_IP>.nip.io      # e.g. rag.4.157.223.24.nip.io
```

`60-ingress.yaml` is committed with this host. **If the ingress IP changes**
(controller reinstalled), update the host in `60-ingress.yaml` and regenerate
the cert below.

## 3. Create a TLS certificate

### Test grade — self-signed (browser will warn; `curl -k`)

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST"

kubectl -n rag-chatbot create secret tls rag-tls \
  --cert=tls.crt --key=tls.key \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Production — trusted cert via cert-manager + Let's Encrypt

With a **real domain** pointed at the ingress IP:

```bash
# install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
```

Create a `ClusterIssuer` (ACME/Let's Encrypt, HTTP-01 solver via the nginx
class), then add this annotation to `60-ingress.yaml` and set a real host:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
```

cert-manager will obtain and renew a trusted cert into `rag-tls` automatically —
remove the self-signed secret first.

## 4. Apply the ingress

```bash
kubectl apply -f k8s/60-ingress.yaml
curl -k https://$HOST/_stcore/health     # 200
```
