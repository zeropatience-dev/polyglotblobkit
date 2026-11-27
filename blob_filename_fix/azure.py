"""Adapter for an existing synchronous Azure SDK ContainerClient."""
from . import (METADATA_KEY, new_key, validate_key, validate_filename, encode_filename,
               decode_filename, content_disposition)
from .limits import DEFAULT_MAX_UPLOAD_MB, UploadSizeLimiter


class AzureFilenameStorage:
    def __init__(self, container_client, *, max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB):
        self.container = container_client
        self.limiter = UploadSizeLimiter(max_upload_mb)

    def upload(self, filename: str, data) -> str:
        """Upload bytes or a binary stream as a new block blob; never overwrite."""
        metadata = {METADATA_KEY: encode_filename(filename)}
        key = new_key()
        with self.limiter.checked(data) as checked_data:
            self.container.get_blob_client(key).upload_blob(
                checked_data, blob_type='BlockBlob', metadata=metadata, overwrite=False)
        return key

    def download(self, key: str):
        """Return (original filename, StorageStreamDownloader). Caller authorizes first."""
        downloader = self.container.get_blob_client(validate_key(key)).download_blob()
        metadata = downloader.properties.metadata or {}
        if METADATA_KEY not in metadata:
            raise ValueError('Missing original filename metadata; legacy blob?')
        return decode_filename(metadata[METADATA_KEY]), downloader

    def download_headers(self, filename: str) -> dict:
        return {'Content-Disposition': content_disposition(filename),
                'Content-Type': 'application/octet-stream',
                'X-Content-Type-Options': 'nosniff'}

    def delete(self, key: str) -> None:
        self.container.get_blob_client(validate_key(key)).delete_blob()

    def download_legacy(self, blob_name: str, *, original_filename: str | None = None):
        """Read an authorized existing blob by its exact, unencoded SDK name.

        No renaming, normalization, URL decoding or automatic legacy fallback.
        Prefer an authoritative original filename from the application when known.
        """
        if not isinstance(blob_name, str) or not blob_name:
            raise ValueError('Expected a non-empty existing blob name')
        if original_filename is not None:
            validate_filename(original_filename)
        downloader = self.container.get_blob_client(blob_name).download_blob()
        metadata = downloader.properties.metadata or {}
        if original_filename is not None:
            name = original_filename
        elif METADATA_KEY in metadata:
            name = decode_filename(metadata[METADATA_KEY])
        else:
            name = validate_filename(blob_name.rsplit('/', 1)[-1])
        return name, downloader
