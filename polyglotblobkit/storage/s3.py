"""S3-compatible synchronous adapter (AWS S3 and modern MinIO endpoints)."""
from polyglotblobkit import (METADATA_KEY, new_key, validate_key, validate_filename,
    encode_filename, decode_filename, content_disposition, UploadSizeLimiter,
    DEFAULT_MAX_UPLOAD_MB, Config)

# AWS single PutObject ceiling; no implicit multipart or unconditional fallback.
MAX_SINGLE_PUT_MB = 5000


class S3FilenameStorage:
    """Use a trusted, preconfigured boto3 S3 client and one dedicated bucket.

    Requires conditional PutObject support (If-None-Match: *). Never retries
    without that condition. Native SDK exceptions and delete semantics are kept.
    """
    def __init__(self, client, bucket: str, *, max_upload_mb=DEFAULT_MAX_UPLOAD_MB):
        if not isinstance(bucket, str) or not bucket or bucket != bucket.strip():
            raise ValueError('Expected a configured bucket name')
        self.client, self.bucket = client, bucket
        self.limiter = UploadSizeLimiter(max_upload_mb)
        if max_upload_mb > MAX_SINGLE_PUT_MB:
            raise ValueError('S3 preview supports at most 5000 MB per upload')
        self.legacy_enabled = True

    @classmethod
    def from_config(cls, client, bucket, config: Config, *, allow_unlimited_uploads=False):
        if not isinstance(config, Config):
            raise TypeError('Expected Config')
        if not config.modules.backend_limiter:
            # Single PUT has a hard ceiling; never pretend unlimited is supported.
            raise ValueError('S3 preview requires a server-side upload limit')
        result = cls(client, bucket, max_upload_mb=config.max_upload_mb)
        result.legacy_enabled = config.modules.legacy_support
        return result

    def upload(self, filename: str, data) -> str:
        metadata = {METADATA_KEY: encode_filename(filename)}
        key = new_key()
        with self.limiter.checked(data) as checked:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=checked,
                Metadata=metadata, IfNoneMatch='*', ContentType='application/octet-stream')
        return key

    def _get(self, key, original_filename=None, *, legacy=False):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response['Body']
        try:
            metadata = response.get('Metadata') or {}
            if original_filename is not None:
                filename = original_filename
            elif METADATA_KEY in metadata:
                filename = decode_filename(metadata[METADATA_KEY])
            elif legacy:
                filename = validate_filename(key.rsplit('/', 1)[-1])
            else:
                raise ValueError('Missing original filename metadata; legacy object?')
            return filename, body
        except BaseException:
            body.close()
            raise

    def download(self, key: str):
        return self._get(validate_key(key))

    def download_legacy(self, object_name: str, *, original_filename=None):
        if not self.legacy_enabled:
            raise ValueError('Legacy access is disabled by configuration')
        if not isinstance(object_name, str) or not object_name:
            raise ValueError('Expected a non-empty existing object name')
        if original_filename is not None:
            validate_filename(original_filename)
        return self._get(object_name, original_filename, legacy=True)

    def download_headers(self, filename):
        return {'Content-Disposition': content_disposition(filename),
                'Content-Type': 'application/octet-stream',
                'X-Content-Type-Options': 'nosniff'}

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=validate_key(key))


class MinioFilenameStorage(S3FilenameStorage):
    """MinIO through its S3-compatible API; pass a boto3 client configured for MinIO.

    No native MinIO SDK dependency. Endpoint and credentials belong to trusted
    deployment configuration. Conditional-write support must be verified.
    """
