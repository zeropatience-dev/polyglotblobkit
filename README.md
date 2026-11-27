# Universal Blob Filename Fix

An open-source reference library for separating technical object keys from human filenames. **Prototype v0.2.0**; not an official Azure fix or production-certified service.

## Design

- New objects use random UUIDv4 keys (32 lowercase ASCII hexadecimal characters), with no extension.
- The exact original Unicode filename is preserved as UTF-8 encoded into Base64 ASCII metadata (`original_filename_b64`). No Unicode normalization or transliteration is performed.
- Uploads enforce a configurable per-file size limit (50 MB by default).
- Uploads never overwrite an existing key. A collision fails; retry using a new upload if appropriate.
- Downloads recover the original filename and expose an RFC 8187 HTTP attachment header.
- The core has no external dependencies. Azure is the only implemented backend; S3, MinIO and .NET ports are possible future additions.

## Local tests (no cloud credentials or dependencies)

Requires Python 3.10 or newer.

```sh
python -m unittest discover -s tests -v
```

## Azure integration example

Install locally: `python -m pip install '.[azure]'` (not published to PyPI).

Create a private container beforehand. Authenticate using your approved method, e.g. a connection string stored in an environment variable for this example. Never commit credentials.

```python
import os
from azure.storage.blob import ContainerClient
from blob_filename_fix.azure import AzureFilenameStorage

container = ContainerClient.from_connection_string(
    os.environ['AZURE_STORAGE_CONNECTION_STRING'], 'documents')
storage = AzureFilenameStorage(container, max_upload_mb=50)

with open('local.pdf', 'rb') as f:
    key = storage.upload('合同_😀.pdf', f)
# Persist the key and ownership/authorization information in the application.
# Authorize the caller before accessing the key.
name, stream = storage.download(key)
headers = storage.download_headers(name)
# For HTTP responses stream.chunks() can be streamed with these headers.
# Do not treat name as a trusted filesystem path.
```

## Upload size limiter (v0.2.0)

The default limit is **50 MB per file**, including for existing constructor calls. Configure a positive integer number of decimal megabytes (`1 MB = 1,000,000 bytes`). Exactly the limit is accepted; one byte above it is rejected. Downloads and existing objects are unaffected. Applications upgrading from v0.1.0 should explicitly choose their desired limit if 50 MB is too low.

```python
from blob_filename_fix import UploadTooLargeError
from blob_filename_fix.azure import AzureFilenameStorage

storage = AzureFilenameStorage(container, max_upload_mb=100)
try:
    key = storage.upload('合同.pdf', incoming_binary_stream)
except UploadTooLargeError as exc:
    # Return HTTP 413 (Content Too Large) in your web framework.
    print(str(exc))
```

The storage-independent `UploadSizeLimiter` can also be used by future adapters:

```python
from blob_filename_fix import UploadSizeLimiter

with UploadSizeLimiter(100).checked(incoming_binary_stream) as checked_data:
    # Pass checked_data to a synchronous storage writer here.
    pass
```

The limiter checks bytes directly or reads a binary stream from its current position. Streams (including non-seekable streams) are staged locally, up to 1 MiB in memory before spilling to temporary disk; oversized streams are stopped after at most limit + 1 bytes for compliant readers. Nothing is sent to Azure until validation passes. The staging file is closed on success and error, and the caller's stream remains open. Staging adds disk I/O and requires sufficient protected temporary storage. Use the checked data only inside its context. Do not rely on a client-reported Content-Length alone.

This is a per-file limit, not a per-request, user or tenant quota. Configure request-body limits, timeouts, concurrency and disk quotas separately at your gateway/framework. Direct cloud uploads or other code paths that bypass this adapter are not covered. HTTP 413 mapping is the integrating application's responsibility; this library does not provide a web server.

## Security and scope

The library is not an access-control layer. UUIDs are not credentials; the application must enforce authorization, quotas, malware checks, retention and tenant isolation. Base64 is not encryption; do not store confidential filenames in metadata if your threat model forbids that. Metadata may be visible to principals with blob read access. This library rejects path separators and control characters and imposes a 1024-byte UTF-8 filename limit (a library policy, not an Azure filename limit). Windows and other local filesystems may impose additional restrictions; never blindly write the recovered name to disk. Metadata must be preserved when copying blobs. The application should store the key durably and handle failed uploads or orphan objects. Legacy blobs are not modified or automatically migrated; keep the existing retrieval path for them. The mock-based tests verify the SDK call contract but are not a real Azure integration test. Validate against a test account or emulator before production use.

## Public repository

The archive contains source, tests, MIT license and GitHub Actions configuration. To publish to a new empty GitHub repository (you need a GitHub account with permission):

```sh
git init -b main
git add .
git commit -m "Initial reference implementation"
git remote add origin https://github.com/YOUR-ACCOUNT/universal-blob-filename-fix.git
git push -u origin main
```

Choose Public when creating the empty repository if it should be available to everyone. The project name has not been reserved. No remote repository or PyPI distribution has been created.

## Deutsch

Dateinamen in allen Sprachen bleiben unverändert in Metadaten erhalten; der technische Blob-Name besteht ausschließlich aus einer UUID. Die Python-Referenzbibliothek ist unabhängig von internen Anwendungen. Ein Azure-Adapter ist enthalten. Andere Speicheranbieter benötigen eigene Adapter. Bestehende Dateien werden nicht verändert; die aufrufende Anwendung muss die Bibliothek integrieren. Seit v0.2.0 gilt ein konfigurierbares Upload-Limit von standardmäßig 50 MB pro Datei (1 MB = 1.000.000 Bytes). Zu große Dateien werden vor dem Cloud-Upload abgelehnt. Kein Live-Test gegen Azure durchgeführt.

## References

- [Azure naming rules](https://learn.microsoft.com/en-us/rest/api/storageservices/naming-and-referencing-containers--blobs--and-metadata)
- [Azure Python BlobClient](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobclient)
- [RFC 8187](https://www.rfc-editor.org/rfc/rfc8187)
