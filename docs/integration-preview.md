# 0.8.0 integration preview

The integration branch starts from the 0.7 storage preview and retains its history.
The source of the earlier 0.5 REST prototype was unavailable; the HTTP module is a
new implementation, not a verified merge or backward-compatible API replacement.
The existing library and browser imports remain independent. Install the optional
HTTP module with `pip install '.[http,test]'` (add `azure` or `s3` for live providers).

## HTTP contract

`polyglotblobkit.http.api.create_app(gateway)` accepts a trusted, preconfigured
`TenantGateway`. No anonymous upload routes, user-supplied endpoints, policies,
credentials or grants. The API never issues tokens. All file operations require an
API-specific Bearer access token. TLS must be supplied by the deployment.

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | process liveness only |
| GET | `/v1/tenants/{tenant}/policy` | authorized browser policy |
| POST | `/v1/tenants/{tenant}/files` | raw binary upload, returns key and byte count |
| GET | `/v1/tenants/{tenant}/files/{key}` | streaming attachment |
| DELETE | `/v1/tenants/{tenant}/files/{key}` | authorized deletion (204) |

POST uses `Content-Type: application/octet-stream` and `X-PBK-Filename-B64`
with standard padded Base64 of the exact UTF-8 filename. The header avoids
putting filenames in URLs; it is not encryption. Do not log this header or the
Authorization header. No multipart or compressed request bodies are accepted.
Example (after configuring the server; use real TLS in deployment):

```python
import base64, os, httpx
filename = 'Rechnung_東京.pdf'
headers = {'Authorization': 'Bearer '+os.environ['PBK_ACCESS_TOKEN'],
           'Content-Type': 'application/octet-stream',
           'X-PBK-Filename-B64': base64.b64encode(filename.encode('utf-8')).decode('ascii')}
with open('local.pdf','rb') as f:
    r = httpx.post('https://YOUR-GATEWAY/v1/tenants/company-a/files', headers=headers, content=f)
r.raise_for_status()
key = r.json()['key']
```

Stable JSON error codes include 401 UNAUTHENTICATED, 403 ACCESS_DENIED,
413 UPLOAD_TOO_LARGE (with limit_bytes), 429 RATE_LIMIT_EXCEEDED, 415 for
unsupported body/signature, and 503 OPERATION_FAILED for unexpected provider
errors (including missing objects in this preview). The caller should map
UPLOAD_TOO_LARGE to the existing locale catalog using limit_bytes. No provider
error details are returned; after streaming headers are sent, a download failure
can only interrupt the response, not change the HTTP status. No idempotency key
or automatic retry; an ambiguous provider timeout can leave an orphan object.

Authorization and rate limiting precede reading the upload body. The HTTP layer
checks actual bytes, not only Content-Length, and stages before writing. The
security and storage layers may stage again: provision protected temporary disk
for up to three concurrent copies per upload, plus overhead. The default
HTTP upload concurrency limit is four per process. Rate limit and concurrency
limit are not shared across workers. Reverse proxies and hosting layers need
independent request size, header size, connection, timeout, disk and unauthenticated
rate limits. Do not bypass the gateway with unrestricted SAS or storage credentials.

`check_signatures=True` is an optional small PDF/PNG/JPEG extension/signature
allowlist. It is off by default to avoid restricting existing supported formats.
It is not a parser, MIME verification or malware scan. Downloads are intentionally
`application/octet-stream` with `nosniff`; MIME preservation, preview and suffix-based
workflow compatibility remain pending. No legacy raw key or path is exposed by HTTP.

## Docker (prepared, not locally built)

`docker build -t polyglotblobkit:0.8-preview .` builds an optional HTTP image.
The default factory `polyglotblobkit.http.deploy:create_app` is a **single-tenant,
single-granted-identity example**, not a production deployment or dynamic tenant
admin API. A multi-tenant installation supplies its own trusted factory with distinct
storage and scoped credentials per tenant. Configure TLS, network isolation and
resource quotas before using it outside a test environment. Container process is
non-root, access logging disabled, one worker. Do not expose the service directly
to the Internet. No private key or cloud credential should be included in the image.

Required environment: `PBK_TENANT`, `PBK_ISSUER`, `PBK_AUDIENCE`, `PBK_SUBJECT`,
`PBK_PUBLIC_KEY_FILE` (mounted PEM public key), `PBK_CONFIG` (mounted JSON policy),
`PBK_PROVIDER` (`azure`, `s3` or `minio`), `PBK_RESOURCE_ID` (canonical physical
resource label), `PBK_PERMISSIONS` (comma-separated subset of upload,download,delete,policy).
For Azure set `AZURE_STORAGE_CONNECTION_STRING` and `PBK_CONTAINER` using secure
runtime secrets; for S3/MinIO set `PBK_BUCKET` and approved boto credential provider;
for MinIO also `PBK_S3_ENDPOINT`. Optional `PBK_REQUESTS_PER_MINUTE`, `PBK_CONCURRENT_UPLOADS`.
No default identity, secret or permissive grants. Production identity integration,
credential rotation and cross-process limits are still open.

## Reversibility

An object's exact original name can be retrieved without this project using standard
Base64 and UTF-8: `base64.b64decode(metadata['original_filename_b64']).decode('utf-8')`.
The object content is unchanged; keys are UUID hex strings. Preserve metadata during
copy and backup. No global file registry is needed; tenant grants/bindings remain
trusted local state. No full export/migration utility or proof of lossless migration
across real providers is included. Do not restore names as unchecked local paths.

## Verification and remaining work

Run `python -m unittest discover -s tests -v` and `node --test web/*.test.mjs`.
HTTP tests use ASGI TestClient/direct ASGI events, simulated storage and real JWT
signature verification. The parallel smoke test exercises 40 uploads and downloads
with eight caller threads and compares SHA-256 contents. It is not a measured cloud
load test or a production capacity benchmark. Network and storage failures are
simulated; no real network failure or ambiguous commit is verified. Existing boto3
contract tests use the SDK Stubber, not AWS. Live Azure, Azurite, AWS and MinIO,
Docker image build, browser UI, multi-process limits, professional translation
review and independent security testing remain unverified. The 0.9 public beta
should not be called production-ready. See prior security and storage notes.
