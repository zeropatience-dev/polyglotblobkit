# Integration quickstart (beta candidate)

Start with the no-cloud Python and browser demos in [README](../README.md).
Choose only the components you need. Use synthetic data and dedicated resources.

## Azure adapter

```sh
python -m pip install '.[azure]'
```

Create a private test container first. Set `AZURE_STORAGE_CONNECTION_STRING`
locally using the emulator or approved test credentials (never commit it).

```python
import os
from azure.storage.blob import ContainerClient
from polyglotblobkit.azure import AzureFilenameStorage

container = ContainerClient.from_connection_string(
    os.environ['AZURE_STORAGE_CONNECTION_STRING'], 'documents')
storage = AzureFilenameStorage(container, max_upload_mb=5)
key = storage.upload('合同_😀.pdf', b'synthetic data')
try:
    name, stream = storage.download(key)
    assert name == '合同_😀.pdf'
    assert stream.readall() == b'synthetic data'
finally:
    storage.delete(key)
```

The integrating application must authorize the caller and persist the key and
ownership information. Explicit legacy reads use the exact SDK blob name rather
than a URL (`storage.download_legacy(name)`). No legacy write/delete migration.
Provider retention or versioning may prevent physical deletion.

For the Azurite suite, start the emulator as described in the
[Microsoft guide](https://learn.microsoft.com/en-us/azure/storage/blobs/use-azurite-to-run-automated-tests),
configure its local connection string, then run:

```sh
python -m unittest discover -s integration -p test_azurite.py -v
```

## S3 / MinIO (optional previews)

Install `python -m pip install '.[s3]'`. See [storage preview](storage-preview.md)
for the adapter example and conditional-write requirements. Configure trusted
credentials and a dedicated test bucket, with `PBK_TEST_S3_BUCKET` and optionally
`PBK_TEST_S3_ENDPOINT` for MinIO. Then run:

```sh
python -m unittest discover -s integration -p test_s3.py -v
```

Without the test bucket the suite skips. Do not run it against production data.
Cloud calls, retained object versions and network transfers may incur costs.

## Optional HTTP gateway

See [HTTP integration preview](integration-preview.md) for the endpoints,
required identity and storage configuration, and Docker build. The standalone
library and browser module do not require this service. The example factory is
single-tenant and single-grant; multi-tenant deployments need trusted bindings,
properly scoped credentials and independent isolation controls. Do not expose
this experimental gateway to the public Internet.
