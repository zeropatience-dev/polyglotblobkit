import io
import logging
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from polyglotblobkit import Config, Modules, new_key, UploadTooLargeError
from polyglotblobkit.security import (TenantPolicy, Binding, Grant, TenantGateway,
    Identity, RS256Verifier, AuthenticationError, AccessDenied, RateExceeded)


class MemoryStorage:
    def __init__(self):
        self.data, self.calls = {}, []
    def upload(self, filename, data):
        self.calls.append('upload')
        key = new_key()
        self.data[key] = (filename, data if isinstance(data, bytes) else data.read())
        return key
    def download(self, key):
        self.calls.append('download')
        return self.data[key]
    def delete(self, key):
        self.calls.append('delete')
        del self.data[key]


class Verifier:
    def verify(self, token):
        if token not in ('alice', 'bob', 'eve', 'other-issuer'):
            raise AuthenticationError('Invalid access token')
        return Identity('other' if token == 'other-issuer' else 'issuer', 'alice' if token == 'other-issuer' else token)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = MemoryStorage(), MemoryStorage()
        self.now = 0
        self.bindings = [Binding(TenantPolicy('a', Config(max_upload_mb=1, locale='de'), 4), 'account/a', self.a),
                         Binding(TenantPolicy('b', Config(max_upload_mb=2, locale='ja'), 10), 'account/b', self.b)]
        self.grants = [Grant(Identity('issuer','alice'), 'a', frozenset({'upload','download','policy'})),
                       Grant(Identity('issuer','bob'), 'b', frozenset({'upload','download','delete','policy'}))]
        self.gateway = self.make()
    def make(self, bindings=None, grants=None):
        return TenantGateway(verifier=Verifier(), bindings=self.bindings if bindings is None else bindings,
            grants=self.grants if grants is None else grants, clock=lambda: self.now)
    def test_round_trip_unicode(self):
        name = '合同_ملف_ä.pdf'
        key = self.gateway.upload('alice','a',name,io.BytesIO(b'file'))
        self.assertEqual(self.gateway.download('alice','a',key),(name,b'file'))
        self.assertEqual(self.b.calls,[])
    def test_unauthenticated_all_actions(self):
        for fn,args in [(self.gateway.upload,('x.pdf',b'x')),(self.gateway.download,(new_key(),)),
                        (self.gateway.delete,(new_key(),)),(self.gateway.browser_policy,())]:
            with self.subTest(fn=fn), self.assertRaises(AuthenticationError): fn('invalid','a',*args)
        self.assertEqual(self.a.calls,[])
    def test_cross_tenant_all_actions(self):
        key = self.gateway.upload('bob','b','x.pdf',b'x')
        for fn,args in [(self.gateway.upload,('x.pdf',b'x')),(self.gateway.download,(key,)),
                        (self.gateway.delete,(key,)),(self.gateway.browser_policy,())]:
            with self.subTest(fn=fn), self.assertRaises(AccessDenied): fn('alice','b',*args)
        self.assertEqual(self.b.calls,['upload'])
    def test_foreign_key_in_own_tenant(self):
        key = self.gateway.upload('bob','b','x.pdf',b'x')
        with self.assertRaises(KeyError): self.gateway.download('alice','a',key)
        self.assertEqual(self.b.calls,['upload'])
    def test_delete_requires_permission(self):
        key = self.gateway.upload('alice','a','x.pdf',b'x')
        with self.assertRaises(AccessDenied): self.gateway.delete('alice','a',key)
        self.assertIn(key,self.a.data)
    def test_authorized_delete(self):
        key = self.gateway.upload('bob','b','x.pdf',b'x')
        self.gateway.delete('bob','b',key)
        self.assertNotIn(key,self.b.data)
    def test_unknown_identity(self):
        with self.assertRaises(AccessDenied): self.gateway.browser_policy('eve','a')
    def test_other_issuer_same_subject(self):
        with self.assertRaises(AccessDenied): self.gateway.browser_policy('other-issuer','a')
    def test_unknown_tenant(self):
        with self.assertRaises(AccessDenied): self.gateway.browser_policy('alice','unknown')
    def test_invalid_tenant(self):
        with self.assertRaises(AccessDenied): self.gateway.browser_policy('alice',[])
    def test_traversal_key(self):
        with self.assertRaises(ValueError): self.gateway.download('alice','a','../b/file')
        self.assertEqual(self.a.calls,[])
    def test_limits_per_tenant(self):
        data = b'x'*1_000_001
        with self.assertRaises(UploadTooLargeError): self.gateway.upload('alice','a','x.pdf',data)
        self.assertEqual(self.a.calls,[])
        self.gateway.upload('bob','b','x.pdf',data)
        self.gateway.upload('alice','a','x.pdf',b'x'*1_000_000)
    def test_oversize_stream_no_write(self):
        with self.assertRaises(UploadTooLargeError): self.gateway.upload('alice','a','x.pdf',io.BytesIO(b'x'*1_000_001))
        self.assertEqual(self.a.calls,[])
    def test_ui_policy(self):
        a = self.gateway.browser_policy('alice','a'); b = self.gateway.browser_policy('bob','b')
        self.assertEqual((a['max_upload_mb'],a['locale']),(1,'de'))
        self.assertEqual((b['max_upload_mb'],b['locale']),(2,'ja'))
        self.assertNotIn('backend_limiter',a['modules'])
    def test_rate_reset_and_tenant_independence(self):
        for _ in range(4): self.gateway.browser_policy('alice','a')
        with self.assertRaises(RateExceeded): self.gateway.browser_policy('alice','a')
        self.gateway.browser_policy('bob','b')
        self.now = 60
        self.gateway.browser_policy('alice','a')
    def test_rate_concurrent(self):
        def call(_):
            try: self.gateway.browser_policy('alice','a'); return True
            except RateExceeded: return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(call,range(20))),4)
    def test_audit_no_secrets(self):
        with self.assertLogs('polyglotblobkit.security.audit',level='INFO') as logs:
            key = self.gateway.upload('alice','a','secret.pdf',b'x')
            with self.assertRaises(AuthenticationError): self.gateway.download('secret-token','bad\nLOG',key)
        out = '\n'.join(logs.output)
        for secret in ('secret.pdf','secret-token',key,'alice','bad\nLOG'): self.assertNotIn(secret,out)
        self.assertIn('outcome=allowed',out); self.assertIn('UNAUTHENTICATED',out)
    def test_duplicate_resources(self):
        with self.assertRaises(ValueError): self.make([self.bindings[0],Binding(TenantPolicy('b'),'account/a',self.b)])
    def test_duplicate_adapter(self):
        with self.assertRaises(ValueError): self.make([self.bindings[0],Binding(TenantPolicy('b'),'account/b',self.a)])
    def test_unknown_grant(self):
        with self.assertRaises(ValueError): self.make(grants=[Grant(Identity('issuer','alice'),'c',frozenset({'upload'}))])
    def test_invalid_permissions(self):
        with self.assertRaises(ValueError): Grant(Identity('issuer','alice'),'a',frozenset({'admin'}))
    def test_no_disabled_backend(self):
        with self.assertRaises(ValueError): TenantPolicy('a',Config(modules=Modules(backend_limiter=False)))

try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

@unittest.skipUnless(HAS_JWT,'Install optional security extra')
class JWTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.other = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pem = cls.private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.verifier = RS256Verifier(public_key_pem=pem,issuer='https://issuer.example',audience='pbk-api')
    def claims(self):
        now = int(time.time())
        return {'iss':'https://issuer.example','aud':'pbk-api','sub':'alice','iat':now-10,'exp':now+60}
    def token(self, claims=None, key=None):
        return jwt.encode(self.claims() if claims is None else claims,self.private if key is None else key,algorithm='RS256')
    def test_valid(self): self.assertEqual(self.verifier.verify(self.token()),Identity('https://issuer.example','alice'))
    def test_forged_signature(self):
        with self.assertRaises(AuthenticationError): self.verifier.verify(self.token(key=self.other))
    def test_invalid_claims(self):
        for changes in ({'exp':1},{'iss':'other'},{'aud':'other'},{'nbf':int(time.time())+500},{'iat':int(time.time())+500},{'sub':''},{'exp':str(int(time.time())+60)},{'exp':None}):
            with self.subTest(changes=changes),self.assertRaises(AuthenticationError): self.verifier.verify(self.token(self.claims()|changes))
    def test_missing_claims(self):
        for key in self.claims():
            claims=self.claims(); del claims[key]
            with self.subTest(key=key),self.assertRaises(AuthenticationError): self.verifier.verify(self.token(claims))
    def test_none_algorithm(self):
        with self.assertRaises(AuthenticationError): self.verifier.verify(jwt.encode(self.claims(),key='',algorithm='none'))
    def test_hmac_algorithm(self):
        with self.assertRaises(AuthenticationError): self.verifier.verify(jwt.encode(self.claims(),key='x'*32,algorithm='HS256'))
    def test_bad_token(self):
        for token in ('not.jwt', '', 'x'*16385, None):
            with self.subTest(token_type=type(token)),self.assertRaises(AuthenticationError): self.verifier.verify(token)

if __name__ == '__main__': unittest.main()
