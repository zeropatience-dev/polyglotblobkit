"""Storage-independent upload size validation (decimal megabytes)."""
from contextlib import contextmanager
from tempfile import SpooledTemporaryFile

BYTES_PER_MB = 1_000_000
DEFAULT_MAX_UPLOAD_MB = 50
_CHUNK_SIZE = 64 * 1024
_SPOOL_THRESHOLD = 1024 * 1024


class UploadTooLargeError(ValueError):
    """Map to HTTP 413 in a web application, if appropriate."""
    code = "UPLOAD_TOO_LARGE"

    def __init__(self, limit_bytes: int):
        self.limit_bytes = limit_bytes
        super().__init__(f'Upload exceeds the {limit_bytes}-byte limit')


class UploadSizeLimiter:
    def __init__(self, max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB):
        if type(max_upload_mb) is not int or max_upload_mb < 1:
            raise ValueError('max_upload_mb must be a positive integer')
        self.max_bytes = max_upload_mb * BYTES_PER_MB

    @contextmanager
    def checked(self, data):
        """Yield verified bytes or a temporary stream; never close caller's stream.

        Read from the current position. Stage streams locally before any remote
        write. Spill to disk above 1 MiB, and read at most limit + 1 bytes from
        compliant binary streams. Temporary storage is released on all exits.
        """
        if isinstance(data, (bytes, bytearray, memoryview)):
            size = data.nbytes if isinstance(data, memoryview) else len(data)
            if size > self.max_bytes:
                raise UploadTooLargeError(self.max_bytes)
            snapshot = bytes(data)
            if len(snapshot) > self.max_bytes:
                raise UploadTooLargeError(self.max_bytes)
            yield snapshot
            return
        if not callable(getattr(data, 'read', None)):
            raise TypeError('Expected bytes or a binary stream')
        with SpooledTemporaryFile(max_size=_SPOOL_THRESHOLD, mode='w+b') as staged:
            total = 0
            while True:
                requested = min(_CHUNK_SIZE, self.max_bytes - total + 1)
                chunk = data.read(requested)
                if not isinstance(chunk, bytes):
                    raise TypeError('Stream read() must return bytes')
                if not chunk:
                    break
                total += len(chunk)
                if total > self.max_bytes:
                    raise UploadTooLargeError(self.max_bytes)
                if len(chunk) > requested:
                    raise ValueError('Stream returned more bytes than requested')
                staged.write(chunk)
            staged.seek(0)
            yield staged
