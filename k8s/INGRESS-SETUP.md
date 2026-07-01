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

## 2. Point DNS at the ingress (domain: shugeinfo.xyz)

`60-ingress.yaml` uses two stable hostnames:

```
UIH=rag.shugeinfo.xyz    # UI  -> rag-ui
APIH=api.shugeinfo.xyz   # API -> rag-api
```

Create/point two **A records** at your DNS provider to the ingress controller's
public IP from step 1:

```
rag.shugeinfo.xyz   A   <INGRESS_IP>
api.shugeinfo.xyz   A   <INGRESS_IP>
```

Verify they resolve before requesting a cert (HTTP-01 needs them live):

```bash
dig +short rag.shugeinfo.xyz    # should print <INGRESS_IP>
dig +short api.shugeinfo.xyz
```

> **On recreate:** the hostnames don't change — only the ingress IP does. So the
> **only** step is repointing these two A records to the new `<INGRESS_IP>`.
> `60-ingress.yaml` needs no edits. (To automate even this, use `external-dns` +
> cert-manager DNS-01 — see the note at the bottom.)

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
that `rag.shugeinfo.xyz` / `api.shugeinfo.xyz` resolve to the ingress IP.

## Optional — auto-manage DNS with external-dns (GoDaddy)

`shugeinfo.xyz` is on **GoDaddy**. Instead of setting the A records by hand,
run **external-dns**, which watches the ingress and keeps
`rag.shugeinfo.xyz` / `api.shugeinfo.xyz` pointed at the ingress IP — including
after a recreate. Certs stay on **HTTP-01** (cert-manager has no native GoDaddy
DNS-01 solver, and HTTP-01 needs no DNS API).

```bash
# 1. Get a PRODUCTION API key+secret: https://developer.godaddy.com/keys
#    (the OTE/test key won't touch real DNS)
kubectl create namespace external-dns
kubectl -n external-dns create secret generic godaddy-credentials \
  --from-literal=GODADDY_API_KEY=<key> \
  --from-literal=GODADDY_API_SECRET=<secret>

# 2. Deploy external-dns
kubectl apply -f k8s/setup/external-dns-godaddy.yaml

# 3. Watch it create the records
kubectl -n external-dns logs deploy/external-dns -f
```

> ⚠️ **GoDaddy API access is gated.** GoDaddy grants production API access only
> to qualifying accounts (historically ~10+ domains, or certain plans). If
> external-dns logs show `ACCESS_DENIED` / 403, your account doesn't have API
> access — just create the two A records manually (step 2 above); the hostnames
> are stable, so it's a one-time task (repoint the IP on recreate).

Fully hands-off recreates (no manual DNS *and* no port-80 dependency) would need
a DNS-01 solver, which for GoDaddy means a community cert-manager webhook —
not wired here due to its maintenance risk. HTTP-01 + external-dns is the
reliable combo.
