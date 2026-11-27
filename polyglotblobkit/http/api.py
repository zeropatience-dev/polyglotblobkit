"""Opt-in REST gateway. Authentication and policy precede body consumption."""
from tempfile import SpooledTemporaryFile
from threading import BoundedSemaphore
import logging

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, StreamingResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
from anyio import CancelScope

from polyglotblobkit import decode_filename, validate_key, content_disposition, UploadTooLargeError
from polyglotblobkit.security import TenantGateway, SecurityError, AuthenticationError

_LOG = logging.getLogger(__name__)

class RequestRejected(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def bearer(request):
    value = request.headers.get('authorization', '')
    scheme, sep, token = value.partition(' ')
    if not sep or scheme.lower() != 'bearer' or not token or len(token) > 16384 or any(c.isspace() for c in token):
        raise AuthenticationError('Invalid access token')
    return token


def error_response(status, code, **extra):
    headers = {'Cache-Control': 'no-store'}
    if status == 401:
        headers['WWW-Authenticate'] = 'Bearer'
    return JSONResponse({'code': code, **extra}, status_code=status, headers=headers)


def signature_matches(filename, head):
    """Optional shallow signature check for a small allowlist; not malware detection."""
    ext = filename.rpartition('.')[2].lower() if '.' in filename else ''
    signatures = {'pdf': (b'%PDF-',), 'png': (b'\x89PNG\r\n\x1a\n',),
                  'jpg': (b'\xff\xd8\xff',), 'jpeg': (b'\xff\xd8\xff',)}
    return ext in signatures and head.startswith(signatures[ext])


class ManagedDownload(StreamingResponse):
    def __init__(self, body, filename):
        self._body = body
        try:
            headers = {'Content-Disposition': content_disposition(filename),
                       'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'}
            if callable(getattr(body, 'chunks', None)):
                chunks = body.chunks()
            elif callable(getattr(body, 'iter_chunks', None)):
                chunks = body.iter_chunks(chunk_size=64 * 1024)
            elif isinstance(body, bytes):
                chunks = iter((body,))
            else:
                raise TypeError('Unsupported download body')
            super().__init__(chunks, media_type='application/octet-stream', headers=headers)
        except BaseException:
            self._close()
            raise

    def _close(self):
        close = getattr(self._body, 'close', None)
        if callable(close):
            close()

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with CancelScope(shield=True):
                await run_in_threadpool(self._close)


def create_app(gateway: TenantGateway, *, max_concurrent_uploads=4, check_signatures=False):
    if not isinstance(gateway, TenantGateway):
        raise TypeError('A trusted tenant gateway is required')
    if type(max_concurrent_uploads) is not int or not 1 <= max_concurrent_uploads <= 1000:
        raise ValueError('Invalid concurrency limit')
    if type(check_signatures) is not bool:
        raise ValueError('check_signatures must be boolean')
    slots = BoundedSemaphore(max_concurrent_uploads)
    app = FastAPI(title='PolyglotBlobKit', version='0.8.0-preview', docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.exception_handler(SecurityError)
    async def security_error(request, exc):
        return error_response(exc.status, exc.code)

    @app.exception_handler(UploadTooLargeError)
    async def too_large(request, exc):
        return error_response(413, exc.code, limit_bytes=exc.limit_bytes)

    @app.exception_handler(RequestRejected)
    async def rejected(request, exc):
        return error_response(exc.status, exc.code)

    @app.exception_handler(ClientDisconnect)
    async def disconnected(request, exc):
        return error_response(400, 'UPLOAD_INTERRUPTED')

    @app.exception_handler(Exception)
    async def internal(request, exc):
        _LOG.warning('HTTP operation failed; exception type=%s', type(exc).__name__)
        return error_response(503, 'OPERATION_FAILED')

    @app.get('/health')
    def health():
        return {'status': 'alive'}  # liveness only; not storage readiness

    @app.get('/v1/tenants/{tenant}/policy')
    def policy(tenant: str, request: Request):
        return JSONResponse(gateway.browser_policy(bearer(request), tenant), headers={'Cache-Control':'no-store'})

    @app.post('/v1/tenants/{tenant}/files', status_code=201)
    async def upload(tenant: str, request: Request):
        token = bearer(request)
        # Authorization and per-tenant rate limit happen before reading request bytes.
        with gateway.upload_session(token, tenant) as (limit, write):
            if request.headers.get('content-encoding', 'identity').lower() != 'identity':
                raise RequestRejected(415, 'UNSUPPORTED_ENCODING')
            if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/octet-stream':
                raise RequestRejected(415, 'EXPECTED_BINARY_BODY')
            names = request.headers.getlist('x-pbk-filename-b64')
            try:
                if len(names) != 1 or len(names[0]) > 1368:
                    raise ValueError('Expected one filename')
                filename = decode_filename(names[0])
            except (ValueError, UnicodeError):
                raise RequestRejected(400, 'INVALID_FILENAME') from None
            declared = request.headers.get('content-length')
            if declared is not None:
                if not declared.isascii() or not declared.isdecimal() or len(declared) > 20:
                    raise RequestRejected(400, 'INVALID_CONTENT_LENGTH')
                if int(declared) > limit:
                    raise UploadTooLargeError(limit)
            if not slots.acquire(blocking=False):
                raise RequestRejected(503, 'UPLOAD_CAPACITY_EXCEEDED')
            try:
                with SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b') as staged:
                    total = 0
                    async for chunk in request.stream():
                        total += len(chunk)
                        if total > limit:
                            raise UploadTooLargeError(limit)
                        if chunk:
                            await run_in_threadpool(staged.write, chunk)
                    if declared is not None and total != int(declared):
                        raise RequestRejected(400, 'CONTENT_LENGTH_MISMATCH')
                    await run_in_threadpool(staged.seek, 0)
                    if check_signatures:
                        head = await run_in_threadpool(staged.read, 16)
                        if not signature_matches(filename, head):
                            raise RequestRejected(415, 'FILE_SIGNATURE_REJECTED')
                        await run_in_threadpool(staged.seek, 0)
                    key = await run_in_threadpool(write, filename, staged)
                    return JSONResponse({'key': key, 'size_bytes': total}, status_code=201,
                                        headers={'Cache-Control':'no-store'})
            finally:
                slots.release()

    def checked_key(key):
        try:
            return validate_key(key)
        except ValueError:
            raise RequestRejected(400, 'INVALID_KEY') from None

    @app.get('/v1/tenants/{tenant}/files/{key}')
    def download(tenant: str, key: str, request: Request):
        token = bearer(request)
        filename, body = gateway.download(token, tenant, checked_key(key))
        return ManagedDownload(body, filename)

    @app.delete('/v1/tenants/{tenant}/files/{key}', status_code=204)
    def delete(tenant: str, key: str, request: Request):
        gateway.delete(bearer(request), tenant, checked_key(key))
        return Response(status_code=204, headers={'Cache-Control':'no-store'})

    return app
