"""Storage-independent UUID keys and lossless UTF-8 filename metadata."""
import base64
import re
import uuid
from urllib.parse import quote

METADATA_KEY = 'original_filename_b64'
MAX_FILENAME_BYTES = 1024


def validate_filename(name: str) -> str:
    """Accept a filename, not a path. Preserve its exact Unicode spelling."""
    if not isinstance(name, str) or not name or name in ('.', '..'):
        raise ValueError('A non-empty filename is required')
    if any(c in name for c in '/\\') or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in name):
        raise ValueError('Paths and control characters are not allowed')
    if len(name.encode('utf-8')) > MAX_FILENAME_BYTES:
        raise ValueError('Filename exceeds the 1024 UTF-8 byte project limit')
    return name


def new_key() -> str:
    return uuid.uuid4().hex


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{32}', key):
        raise ValueError('Expected a 32-character lowercase hexadecimal key')
    return key


def encode_filename(name: str) -> str:
    return base64.b64encode(validate_filename(name).encode('utf-8')).decode('ascii')


def decode_filename(value: str) -> str:
    return validate_filename(base64.b64decode(value, validate=True).decode('utf-8'))


def content_disposition(name: str) -> str:
    """ASCII-only HTTP attachment header with a Unicode filename (RFC 8187)."""
    name = validate_filename(name)
    return "attachment; filename=\"download\"; filename*=UTF-8''" + quote(name, safe='')


from .limits import UploadSizeLimiter, UploadTooLargeError, DEFAULT_MAX_UPLOAD_MB
