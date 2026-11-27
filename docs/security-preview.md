# 0.6 security module preview (based on v0.4.0)

This is a feature branch, not a production release or a merge of the 0.5 REST prototype. Existing imports and standalone UI modules are unchanged. Install `pip install '.[security]'` for the optional static RS256 verifier. The tenant gateway uses a trusted identity verifier, immutable local policy and grants, a distinct storage adapter and canonical physical resource ID for each tenant, and deny-by-default permissions. A tenant ID or UUID is never a credential. Access is granted per tenant, not per individual document: an authorized reader can read any known object key in that tenant. No unrestricted legacy lookup is provided.

## Integrator obligations

- Use a distinct Azure container or account for each tenant and separate credentials with minimal scope. The binding's resource ID must identify the actual resource; duplicate IDs and adapter instances are rejected, but aliases or falsely configured resource IDs cannot be detected. Do not expose raw storage adapters, account keys or unrestricted SAS links to callers. Configure Azure network access and RBAC independently.
- Use verified API access tokens, not ID tokens. Static RS256 verifier pins key, issuer and API audience and verifies signature, expiry, issued-at and optional not-before. No OIDC discovery, JWKS rotation, revocation, Entra-specific claims validation or token acquisition is implemented. Configure an issuer that provides API-specific tokens; use a production-grade identity adapter for real deployments.
- Grants and storage bindings are constructed by trusted server configuration. Never populate them from HTTP requests. Grant changes require rebuilding/restarting the gateway; no admin HTTP API or persistence yet.
- Per-tenant fixed-window rate limit covers authorized calls only and is process-local; it resets on restart and is not a distributed DoS defense. Enforce unauthenticated limits, concurrency, timeouts, request body limits and disk quotas at the reverse proxy/API. No storage quotas, cross-worker coordination or malware scanning yet.
- Uploads are staged and checked before a storage write; the existing Azure adapter may stage streams again. Configure its own maximum at least as high as the tenant maximum, and budget local disk. Use TLS, storage encryption and proper download response handling. A successful download audit event means the download was authorized and initiated, not that streaming completed.
- Audit events go to a local Python logger (`polyglotblobkit.security.audit`); enable INFO and configure retention and restricted access. No tokens, filenames, UUIDs or user identities are recorded, and no telemetry is sent. This is not an immutable audit ledger; storage/HTTP logs and incident response are separate requirements.
- Map security exceptions to their `status` and `code` (401/403/429), size errors to 413; never expose stack traces or storage internals. Do not trust client-supplied policies. A new token and explicit grant are checked on every call. Existing direct adapters are intentionally not wrapped automatically.

## Example (trusted application startup)

```python
from polyglotblobkit import Config
from polyglotblobkit.azure import AzureFilenameStorage
from polyglotblobkit.security import (
    Binding, Grant, Identity, RS256Verifier, TenantGateway, TenantPolicy,
)

# Provision separate, minimally scoped ContainerClient instances first.
policy = Config(max_upload_mb=5, locale='de')
verifier = RS256Verifier(public_key_pem=public_key_pem,
                         issuer=trusted_issuer, audience=api_audience)
gateway = TenantGateway(
    verifier=verifier,
    bindings=[Binding(TenantPolicy('company-a', policy, 60),
                      'account-a/container-a',
                      AzureFilenameStorage.from_config(container_a, policy))],
    grants=[Grant(Identity(trusted_issuer, verified_subject), 'company-a',
                  frozenset({'upload', 'download', 'policy'}))],
)
# Request handling: token comes from HTTP Authorization, tenant from route.
key = gateway.upload(access_token, 'company-a', 'Rechnung_東京.pdf', file_stream)
```

## Pending before production

Merge and secure the REST API; integration tests with real Azure tenant containers and scoped credentials; distributed limits and quotas; identity-provider integration and key lifecycle; external penetration/security review; deployment documentation. Do not advertise the preview as a secure multi-tenant service without these checks.
