"""Explicit tenant bindings, deny by default, per-tenant policy and local audit."""
from dataclasses import dataclass, field
from contextlib import contextmanager
from threading import Lock
from time import monotonic
import logging
import re
from typing import Protocol

from polyglotblobkit import validate_key, validate_filename
from polyglotblobkit.config import Config
from polyglotblobkit.limits import UploadSizeLimiter, UploadTooLargeError
from .tokens import Identity, SecurityError, AuthenticationError

_PERMISSIONS = frozenset({'upload', 'download', 'delete', 'policy'})
_LOG = logging.getLogger('polyglotblobkit.security.audit')


class AccessDenied(SecurityError):
    code = 'ACCESS_DENIED'
    status = 403


class RateExceeded(SecurityError):
    code = 'RATE_LIMIT_EXCEEDED'
    status = 429


class Storage(Protocol):
    def upload(self, filename, data): ...
    def download(self, key): ...
    def delete(self, key): ...


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str
    config: Config = field(default_factory=Config)
    requests_per_minute: int = 60

    def __post_init__(self):
        if not isinstance(self.tenant_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', self.tenant_id):
            raise ValueError('Invalid tenant ID')
        if not isinstance(self.config, Config) or not self.config.modules.backend_limiter:
            raise ValueError('Tenant gateway requires a server-side upload limit')
        if type(self.requests_per_minute) is not int or not 1 <= self.requests_per_minute <= 1_000_000:
            raise ValueError('Invalid request limit')


@dataclass(frozen=True)
class Binding:
    policy: TenantPolicy
    resource_id: str  # trusted canonical physical resource ID, never client input
    storage: Storage

    def __post_init__(self):
        if not isinstance(self.policy, TenantPolicy) or not isinstance(self.resource_id, str) or not self.resource_id.strip():
            raise ValueError('Invalid trusted storage binding')
        if self.resource_id != self.resource_id.strip().lower():
            raise ValueError('Use a canonical lowercase resource ID')
        if not all(callable(getattr(self.storage, p, None)) for p in ('upload','download','delete')):
            raise ValueError('Storage adapter must support upload/download/delete')


@dataclass(frozen=True)
class Grant:
    identity: Identity
    tenant_id: str
    permissions: frozenset[str]

    def __post_init__(self):
        if not isinstance(self.identity, Identity) or not isinstance(self.tenant_id, str):
            raise ValueError('Invalid grant')
        if not isinstance(self.permissions, frozenset) or not self.permissions or not self.permissions <= _PERMISSIONS:
            raise ValueError('Unknown or invalid permissions')


class TenantGateway:
    """All calls authenticate and authorize before touching a storage adapter.

    Trusted server config only. Separate physical storage and scoped credentials
    per tenant are mandatory deployment invariants; resource labels cannot prove
    actual storage separation. No raw legacy names exposed here.
    """
    def __init__(self, *, verifier, bindings, grants, clock=monotonic):
        if not callable(getattr(verifier, 'verify', None)):
            raise ValueError('A trusted identity verifier is required')
        self._verifier, self._clock = verifier, clock
        self._bindings, self._grants, self._windows = {}, {}, {}
        self._lock = Lock()
        resources, adapters = set(), set()
        for binding in bindings:
            if not isinstance(binding, Binding):
                raise ValueError('Expected trusted binding')
            tenant = binding.policy.tenant_id
            if tenant in self._bindings or binding.resource_id in resources or id(binding.storage) in adapters:
                raise ValueError('Duplicate tenant or storage binding')
            self._bindings[tenant] = binding
            resources.add(binding.resource_id)
            adapters.add(id(binding.storage))
        for grant in grants:
            if not isinstance(grant, Grant) or grant.tenant_id not in self._bindings:
                raise ValueError('Grant references unknown tenant')
            key = (grant.identity, grant.tenant_id)
            if key in self._grants:
                raise ValueError('Duplicate grant')
            self._grants[key] = grant.permissions

    def _rate(self, policy):
        # Per process, fixed 60-second window; bounded by configured tenant count.
        with self._lock:
            now = self._clock()
            start, count = self._windows.get(policy.tenant_id, (now, 0))
            if now - start >= 60:
                start, count = now, 0
            if count >= policy.requests_per_minute:
                raise RateExceeded('Request limit exceeded')
            self._windows[policy.tenant_id] = (start, count + 1)

    def _authorize(self, token, tenant, action):
        identity = self._verifier.verify(token)
        if not isinstance(identity, Identity):
            raise AuthenticationError('Invalid verified identity')
        if not isinstance(tenant, str) or len(tenant) > 63:
            raise AccessDenied('Access denied')
        if action not in self._grants.get((identity, tenant), frozenset()):
            raise AccessDenied('Access denied')
        binding = self._bindings[tenant]
        self._rate(binding.policy)
        return binding

    def _run(self, token, tenant, action, operation):
        # Avoid logging arbitrary tenant strings, tokens, identities, filenames or keys.
        known = tenant if isinstance(tenant, str) and len(tenant) <= 63 and tenant in self._bindings else '-'
        try:
            binding = self._authorize(token, tenant, action)
            result = operation(binding)
        except (SecurityError, UploadTooLargeError) as exc:
            _LOG.info('action=%s tenant=%s outcome=denied code=%s', action, known, exc.code)
            raise
        except Exception:
            _LOG.warning('action=%s tenant=%s outcome=failed', action, known)
            raise
        _LOG.info('action=%s tenant=%s outcome=allowed', action, known)
        return result

    def browser_policy(self, token, tenant):
        return self._run(token, tenant, 'policy', lambda b: b.policy.config.browser_policy())

    @contextmanager
    def upload_session(self, token, tenant):
        """Authorize and rate-limit before an HTTP body is consumed.

        Yield the trusted byte limit and a single-use synchronous writer.
        The writer must be used within this context, by trusted server code.
        """
        known = tenant if isinstance(tenant, str) and len(tenant) <= 63 and tenant in self._bindings else '-'
        used = False
        active = True
        completed = False
        try:
            binding = self._authorize(token, tenant, 'upload')
            limiter = UploadSizeLimiter(binding.policy.config.max_upload_mb)
            def write(filename, data):
                nonlocal used, completed
                if not active or used:
                    raise RuntimeError('Upload session unavailable')
                used = True
                validate_filename(filename)
                with limiter.checked(data) as staged:
                    key = validate_key(binding.storage.upload(filename, staged))
                completed = True
                return key
            yield limiter.max_bytes, write
        except (SecurityError, UploadTooLargeError) as exc:
            _LOG.info('action=upload tenant=%s outcome=denied code=%s', known, exc.code)
            raise
        except BaseException:
            _LOG.warning('action=upload tenant=%s outcome=failed', known)
            raise
        finally:
            active = False
        _LOG.info('action=upload tenant=%s outcome=%s', known, 'allowed' if completed else 'abandoned')

    def upload(self, token, tenant, filename, data):
        def operation(b):
            validate_filename(filename)
            with UploadSizeLimiter(b.policy.config.max_upload_mb).checked(data) as staged:
                return validate_key(b.storage.upload(filename, staged))
        return self._run(token, tenant, 'upload', operation)

    def download(self, token, tenant, key):
        return self._run(token, tenant, 'download', lambda b: b.storage.download(validate_key(key)))

    def delete(self, token, tenant, key):
        return self._run(token, tenant, 'delete', lambda b: b.storage.delete(validate_key(key)))
