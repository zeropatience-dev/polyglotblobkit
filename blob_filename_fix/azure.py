"""Adapter for an existing synchronous Azure SDK ContainerClient."""
from . import (METADATA_KEY, new_key, validate_key, validate_filename, encode_filename,
               decode_filename, content_disposition)
from contextlib import nullcontext
from .limits import DEFAULT_MAX_UPLOAD_MB, UploadSizeLimiter
from .config import Config


class AzureFilenameStorage:
    def __init__(self, container_client, *, max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB):
        self.container = container_client
        self.limiter = UploadSizeLimiter(max_upload_mb)
        self.legacy_enabled = True

    @classmethod
    def from_config(cls, container_client, config: Config, *, allow_unlimited_uploads: bool = False):
        """Use trusted server policy only; disabling protection requires explicit opt-in."""
        if not isinstance(config, Config):
            raise TypeError("Expected Config")
        if not config.modules.backend_limiter and allow_unlimited_uploads is not True:
            raise ValueError("Disabling backend limits requires allow_unlimited_uploads=True")
        storage = cls(container_client, max_upload_mb=config.max_upload_mb)
        if not config.modules.backend_limiter:
            storage.limiter = None
        storage.legacy_enabled = config.modules.legacy_support
        return storage

    def upload(self, filename: str, data) -> str:
        """Upload bytes or a binary stream as a new block blob; never overwrite."""
        metadata = {METADATA_KEY: encode_filename(filename)}
        key = new_key()
        with (self.limiter.checked(data) if self.limiter is not None else nullcontext(data)) as checked_data:
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
        if not self.legacy_enabled:
            raise ValueError('Legacy access is disabled by configuration')
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
