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
UIH=rag.<INGRESS_IP>.nip.io       # UI  host, e.g. rag.4.157.223.24.nip.io
APIH=api.<INGRESS_IP>.nip.io      # API host, e.g. api.4.157.223.24.nip.io
```

`60-ingress.yaml` routes the UI host to `rag-ui` and the API host to `rag-api`
(so you can upload/ingest/chat over HTTPS). **If the ingress IP changes**
(controller/cluster reinstalled), update **both** hosts in `60-ingress.yaml` and
regenerate the cert below with both SANs.

## 3. TLS certificate — trusted, auto-issued (cert-manager + Let's Encrypt)

This is the recommended path: cert-manager obtains **and renews** a trusted cert
automatically, so recreates need no manual `openssl`. Let's Encrypt's HTTP-01
challenge works with nip.io hosts (they're publicly resolvable) — no domain
purchase required.

```bash
# a) Install cert-manager (one-time; includes CRDs)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
kubectl -n cert-manager wait --for=condition=available deploy --all --timeout=180s

# b) Set your email in the issuers, then apply them (one-time)
sed -i "s/<YOUR_EMAIL>/you@example.com/" k8s/setup/cert-manager-issuers.yaml
kubectl apply -f k8s/setup/cert-manager-issuers.yaml
```

`60-ingress.yaml` is already annotated with `cert-manager.io/cluster-issuer:
letsencrypt-prod`. When you apply the ingress (step 4), cert-manager sees the
annotation + `tls` block, solves the HTTP-01 challenge, and writes the trusted
cert into the `rag-tls` secret — then renews it before expiry.

> **Testing tip:** Let's Encrypt **prod** has rate limits. While iterating, set
> the annotation to `letsencrypt-staging` first (issues an untrusted cert, so
> the browser still warns, but confirms the flow), then switch to
> `letsencrypt-prod` for the real trusted cert. If you switch issuers, delete
> the `rag-tls` secret so cert-manager re-issues: `kubectl -n rag-chatbot delete secret rag-tls`.

### Fallback — self-signed (offline / no Let's Encrypt access)

If the cluster can't reach Let's Encrypt, remove the `cert-manager.io/...`
annotation and create a self-signed secret instead (browser will warn):

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=$UIH" -addext "subjectAltName=DNS:$UIH,DNS:$APIH"
kubectl -n rag-chatbot create secret tls rag-tls \
  --cert=tls.crt --key=tls.key --dry-run=client -o yaml | kubectl apply -f -
```

## 4. Apply the ingress & verify

```bash
kubectl apply -f k8s/60-ingress.yaml

# cert-manager issuance takes ~1-2 min; watch it become Ready:
kubectl -n rag-chatbot get certificate rag-tls -w        # READY=True when done

# With a trusted cert you can drop the -k:
curl https://$UIH/_stcore/health      # UI  -> 200
curl https://$APIH/v1/health          # API -> 200

# Upload a document over HTTPS (no port-forward / tunnel needed):
curl -X POST https://$APIH/v1/upload \
  -H "X-API-Key: <YOUR_KEY>" -F "file=@yourdoc.pdf"
```

If `kubectl -n rag-chatbot describe certificate rag-tls` shows the challenge
stuck, confirm the ingress is reachable on **port 80** (HTTP-01 needs it) and
that the nip.io host resolves to the ingress IP.
