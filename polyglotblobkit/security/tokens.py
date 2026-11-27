"""Optional fixed-issuer JWT verification; no token-provided key or algorithm."""
from dataclasses import dataclass


class SecurityError(Exception):
    code = 'SECURITY_ERROR'
    status = 403


class AuthenticationError(SecurityError):
    code = 'UNAUTHENTICATED'
    status = 401


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str

    def __post_init__(self):
        for value in (self.issuer, self.subject):
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError('Invalid verified identity')


class RS256Verifier:
    """Trust a configured RSA public key and one issuer/audience, not JWT headers.

    Static key only; operators must arrange rotation and configure an access-token
    audience unique to this API. This is not a complete Entra/OIDC integration.
    """
    def __init__(self, *, public_key_pem, issuer: str, audience: str):
        import jwt
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
        if not isinstance(issuer, str) or not issuer.strip() or not isinstance(audience, str) or not audience.strip():
            raise ValueError('Issuer and audience required')
        key = load_pem_public_key(public_key_pem)
        if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
            raise ValueError('RSA public key of at least 2048 bits required')
        self._key, self._issuer, self._audience, self._jwt = key, issuer, audience, jwt

    def verify(self, token: str) -> Identity:
        if not isinstance(token, str) or not token or len(token) > 16384:
            raise AuthenticationError('Invalid access token')
        try:
            claims = self._jwt.decode(token, self._key, algorithms=['RS256'],
                issuer=self._issuer, audience=self._audience,
                options={'require': ['iss', 'aud', 'sub', 'exp', 'iat']})
            # PyJWT accepts certain numeric strings; require actual integer dates.
            for name in ('exp', 'iat', 'nbf'):
                if name in claims and type(claims[name]) is not int:
                    raise ValueError('Invalid token date')
            return Identity(claims['iss'], claims['sub'])
        except (self._jwt.PyJWTError, ValueError, TypeError, OverflowError):
            raise AuthenticationError('Invalid access token') from None
