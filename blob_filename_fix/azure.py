"""Adapter for an existing synchronous Azure SDK ContainerClient."""
from . import (METADATA_KEY, new_key, validate_key, encode_filename,
               decode_filename, content_disposition)


class AzureFilenameStorage:
    def __init__(self, container_client):
        self.container = container_client

    def upload(self, filename: str, data) -> str:
        """Upload bytes or a binary stream as a new block blob; never overwrite."""
        metadata = {METADATA_KEY: encode_filename(filename)}
        key = new_key()
        self.container.get_blob_client(key).upload_blob(
            data, blob_type='BlockBlob', metadata=metadata, overwrite=False)
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
