"""Shared storage contract; cloud SDKs are optional and never imported here."""
from contextlib import contextmanager
from typing import Protocol, Iterator
from polyglotblobkit.azure import AzureFilenameStorage


class StorageAdapter(Protocol):
    """Server-configured storage binding; authorization is the caller's job."""
    def upload(self, filename: str, data) -> str: ...
    def download(self, key: str) -> tuple[str, object]: ...
    def delete(self, key: str) -> None: ...


@contextmanager
def open_download(storage: StorageAdapter, key: str):
    """Yield (original name, iterator of bytes), without loading the entire file.

    Consume within the context. S3 bodies are explicitly closed; Azure SDK's
    downloader owns its HTTP handling. Other adapters may implement iter_chunks.
    Provider exceptions propagate unchanged.
    """
    filename, body = storage.download(key)
    try:
        if callable(getattr(body, 'chunks', None)):
            chunks = body.chunks()
        elif callable(getattr(body, 'iter_chunks', None)):
            chunks = body.iter_chunks(chunk_size=64 * 1024)
        elif isinstance(body, bytes):
            chunks = iter((body,))
        else:
            raise TypeError('Unsupported download body')
        yield filename, chunks
    finally:
        close = getattr(body, 'close', None)
        if callable(close):
            close()


from .s3 import S3FilenameStorage, MinioFilenameStorage

__all__ = ['StorageAdapter', 'open_download', 'AzureFilenameStorage',
           'S3FilenameStorage', 'MinioFilenameStorage']
