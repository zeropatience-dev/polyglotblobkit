# Storage preview 0.7.0a1

Existing Azure integrations may keep their current adapter. The S3 and MinIO
adapters are optional; MinIO uses boto3 against a trusted S3-compatible endpoint.
The REST prototype is not included in this branch. This is not a production release.

```sh
pip install '.[s3,security]'
```

```python
import boto3
from polyglotblobkit.storage import S3FilenameStorage, open_download
client = boto3.client('s3')  # deployment-managed credentials
storage = S3FilenameStorage(client, 'dedicated-bucket', max_upload_mb=5)
key = storage.upload('合同_Müller.pdf', b'example')
with open_download(storage, key) as (name, chunks):
    for chunk in chunks:
        pass  # forward to authorized download response
storage.delete(key)
```

For MinIO, use `MinioFilenameStorage` and a boto3 client configured with the
trusted endpoint, TLS, credentials and path-style addressing if necessary.
Never accept the endpoint, bucket or credentials from an untrusted request.
The shared contract exposes upload, download and delete; the download streaming
helper manages S3 body closure. Provider exceptions are intentionally not mapped.

## Compatibility limits

- Conditional `PutObject` support (`IfNoneMatch='*'`) is required. Older S3-compatible
  endpoints may reject this request. No unsafe fallback is implemented.
- The adapter uses single PUT only, at most 5,000 decimal MB, with size validation
  and staging before upload. This is not multipart support. Configure much smaller
  limits and bound concurrent requests and temporary disk usage in production.
- Object names are UUIDs; original names are stored as Base64 metadata. Do not
  strip metadata. MIME type is deliberately application/octet-stream; no inline
  rendering or extension preservation is promised.
- S3 deletion may create a delete marker in versioned buckets; retention, legal
  hold and object lock can prevent physical deletion. Azure has separate rules.
- Existing keys are available through explicit legacy reads, not legacy writes or
  deletes. SDK credentials and IAM must restrict each storage binding independently.
- TenantGateway authorization is optional for standalone modules, but mandatory
  or replaced by equivalent application authorization for untrusted callers.

## Integration impact

Low: browser size preflight, translations, backend size validation; no storage
migration required. Medium: REST validation endpoint, legacy reads, rate limits.
Medium/high: UUID storage naming, provider replacement and migration, depending
on existing references and metadata contracts. High: shared multi-tenant gateway,
identity integration and storage isolation. These are estimates, not guarantees.
A closed third-party UI without extension points cannot automatically be patched.

## Tests

`python -m unittest discover -s tests -v` includes fake storage and optional
boto3 Stubber parameter checks, not live S3 or MinIO. To opt in to live tests,
configure a dedicated non-production bucket and least-privilege SDK credentials.
Set `PBK_TEST_S3_BUCKET` and optionally `PBK_TEST_S3_ENDPOINT` for MinIO, then run
`python -m unittest discover -s integration -p test_s3.py -v`. Tests create and
attempt to delete their own random keys; versioned or retained objects may remain.
Azurite, real Azure, real S3/MinIO, browser and production security/load validation
remain outstanding. Do not claim compatibility with any specific external system.
