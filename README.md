# Universal Blob Filename Fix

An open-source reference library for separating technical object keys from human filenames. **Prototype v0.1.0**; not an official Azure fix or production-certified service.

## Design

- New objects use random UUIDv4 keys (32 lowercase ASCII hexadecimal characters), with no extension.
- The exact original Unicode filename is preserved as UTF-8 encoded into Base64 ASCII metadata (`original_filename_b64`). No Unicode normalization or transliteration is performed.
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
storage = AzureFilenameStorage(container)

with open('local.pdf', 'rb') as f:
    key = storage.upload('合同_😀.pdf', f)
# Persist the key and ownership/authorization information in the application.
# Authorize the caller before accessing the key.
name, stream = storage.download(key)
headers = storage.download_headers(name)
# For HTTP responses stream.chunks() can be streamed with these headers.
# Do not treat name as a trusted filesystem path.
```

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

Dateinamen in allen Sprachen bleiben unverändert in Metadaten erhalten; der technische Blob-Name besteht ausschließlich aus einer UUID. Die Python-Referenzbibliothek ist unabhängig von internen Anwendungen. Ein Azure-Adapter ist enthalten. Andere Speicheranbieter benötigen eigene Adapter. Bestehende Dateien werden nicht verändert; die aufrufende Anwendung muss die Bibliothek integrieren. Kein Live-Test gegen Azure durchgeführt.

## References

- [Azure naming rules](https://learn.microsoft.com/en-us/rest/api/storageservices/naming-and-referencing-containers--blobs--and-metadata)
- [Azure Python BlobClient](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobclient)
- [RFC 8187](https://www.rfc-editor.org/rfc/rfc8187)
