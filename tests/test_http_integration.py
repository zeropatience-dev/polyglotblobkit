import asyncio
import base64
import hashlib
import io
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote
from unittest.mock import Mock

from polyglotblobkit import Config, METADATA_KEY, new_key
from polyglotblobkit.security import (AuthenticationError, Binding, Grant, Identity,
    TenantGateway, TenantPolicy)
from polyglotblobkit.storage import S3FilenameStorage, MinioFilenameStorage
from test_storage import FakeS3

try:
    import httpx
    from fastapi.testclient import TestClient
    from polyglotblobkit.http.api import create_app
except ImportError:
    httpx = None


class LockedS3(FakeS3):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.fail = False
    def put_object(self, **kw):
        with self.lock:
            if self.fail:
                raise RuntimeError('private secret backend details')
            return super().put_object(**kw)
    def get_object(self, **kw):
        with self.lock:
            return super().get_object(**kw)
    def delete_object(self, **kw):
        with self.lock:
            return super().delete_object(**kw)


@unittest.skipUnless(httpx is not None, 'Install HTTP and test extras')
class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.backend = LockedS3()
        self.verifier = Mock()
        def verify(token):
            if token not in ('alice','bob','reader'):
                raise AuthenticationError('Invalid token')
            return Identity('issuer',token)
        self.verifier.verify.side_effect = verify
        self.a = S3FilenameStorage(self.backend,'tenant-a',max_upload_mb=1)
        self.b = MinioFilenameStorage(self.backend,'tenant-b',max_upload_mb=2)
        self.gateway = TenantGateway(verifier=self.verifier,
            bindings=[Binding(TenantPolicy('a',Config(max_upload_mb=1,locale='de'),1000),'s3/a',self.a),
                Binding(TenantPolicy('b',Config(max_upload_mb=2,locale='ja'),1000),'s3/b',self.b)],
            grants=[Grant(Identity('issuer','alice'),'a',frozenset({'upload','download','delete','policy'})),
                Grant(Identity('issuer','bob'),'b',frozenset({'upload','download','delete','policy'})),
                Grant(Identity('issuer','reader'),'a',frozenset({'download'}))])
        self.app = create_app(self.gateway, max_concurrent_uploads=16)
        self.client = TestClient(self.app,raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def upload(self, name='合同_e\u0301.pdf', data=b'content', token='alice', tenant='a', client=None, **headers):
        return (client or self.client).post(f'/v1/tenants/{tenant}/files',content=data,
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/octet-stream','X-PBK-Filename-B64':base64.b64encode(name.encode('utf-8')).decode('ascii'),**headers})

    def test_roundtrip_unicode_and_independent_recovery(self):
        for name in ['Müller.pdf','合同.pdf','ملف.pdf','😀 #%.pdf','e\u0301.pdf','é.pdf','İstanbul.pdf']:
            r = self.upload(name)
            self.assertEqual(r.status_code,201,r.text)
            key = r.json()['key']
            metadata, raw = self.backend.objects['tenant-a',key]
            self.assertEqual(base64.b64decode(metadata[METADATA_KEY]).decode('utf-8'),name)
            self.assertEqual(raw,b'content')
            r = self.client.get(f'/v1/tenants/a/files/{key}',headers={'Authorization':'Bearer reader'})
            self.assertEqual(r.content,raw)
            self.assertEqual(unquote(r.headers['content-disposition'].split("UTF-8''")[1]),name)
            self.assertTrue(self.backend.last_body.closed)
            self.assertEqual(self.client.delete(f'/v1/tenants/a/files/{key}',headers={'Authorization':'Bearer alice'}).status_code,204)

    def test_exact_limit_and_unknown_length(self):
        r = self.upload(data=(b'x'*100_000 for _ in range(10)))
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()['size_bytes'],1_000_000)
        r = self.upload(data=(b'x'*100_000 for _ in range(11)))
        self.assertEqual(r.status_code,413,r.text)
        self.assertEqual(len(self.backend.objects),1)

    def test_declared_over_limit(self):
        r=self.upload(data=b'x'*1_000_001)
        self.assertEqual(r.status_code,413)
        self.assertEqual(r.json()['limit_bytes'],1_000_000)
        self.assertEqual(self.backend.calls,[])

    def test_false_content_length(self):
        r=self.upload(data=b'abcdef',**{'Content-Length':'2'})
        self.assertEqual(r.status_code,400)
        self.assertEqual(self.backend.calls,[])

    def test_policy_and_tenant_limits(self):
        for t, token, mb in [('a','alice',1),('b','bob',2)]:
            r=self.client.get(f'/v1/tenants/{t}/policy',headers={'Authorization':'Bearer '+token})
            self.assertEqual(r.json()['max_upload_mb'],mb)
        self.assertEqual(self.upload(data=b'x'*1_000_001,token='bob',tenant='b').status_code,201)
        self.assertEqual(self.upload(data=b'x'*1_000_001).status_code,413)

    def test_permission_and_cross_tenant(self):
        key=self.upload(token='bob',tenant='b').json()['key']
        for method in ('get','delete'):
            r=getattr(self.client,method)(f'/v1/tenants/b/files/{key}',headers={'Authorization':'Bearer alice'})
            self.assertEqual(r.status_code,403)
        self.assertEqual(self.upload(token='reader').status_code,403)
        self.assertEqual(self.upload(token='wrong').status_code,401)
        self.assertEqual(self.upload(token='alice',tenant='b').status_code,403)
        self.assertEqual(len(self.backend.calls),1)

    def test_no_body_read_before_authorization(self):
        async def run():
            sent=[]
            async def receive():
                raise AssertionError('Unauthorized request body was read')
            async def send(m): sent.append(m)
            await self.app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST',
                'scheme':'http','path':'/v1/tenants/b/files','raw_path':b'/v1/tenants/b/files',
                'query_string':b'','root_path':'','headers':[(b'authorization',b'Bearer alice'),(b'content-type',b'application/octet-stream'),(b'x-pbk-filename-b64',b'eC5wZGY=')],
                'client':('test',1),'server':('test',80)},receive,send)
            self.assertEqual(sent[0]['status'],403)
        asyncio.run(run())
        self.assertEqual(self.backend.calls,[])

    def test_invalid_filename_and_encoding(self):
        self.assertEqual(self.upload('../x').status_code,400)
        self.assertEqual(self.upload(**{'Content-Encoding':'gzip'}).status_code,415)
        self.assertEqual(self.upload(**{'Content-Type':'multipart/form-data'}).status_code,415)
        self.assertEqual(self.backend.calls,[])

    def test_signature_optional(self):
        with TestClient(create_app(self.gateway,check_signatures=True)) as c:
            self.assertEqual(self.upload('x.pdf',b'MZfake',client=c).status_code,415)
            self.assertEqual(self.upload('x.pdf',b'%PDF-1.7',client=c).status_code,201)
            self.assertEqual(self.upload('x.zip',b'PK',client=c).status_code,415)
        self.assertEqual(len(self.backend.objects),1)

    def test_storage_failure_redacted_then_recovery(self):
        self.backend.fail=True
        r=self.upload()
        self.assertEqual(r.status_code,503)
        self.assertEqual(r.json(),{'code':'OPERATION_FAILED'})
        self.backend.fail=False
        self.assertEqual(self.upload().status_code,201)

    def test_interrupted_body_no_cloud_write(self):
        async def run():
            events=iter([{'type':'http.request','body':b'first','more_body':True},{'type':'http.disconnect'}]); sent=[]
            async def receive(): return next(events)
            async def send(m): sent.append(m)
            await self.app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST',
                'scheme':'http','path':'/v1/tenants/a/files','raw_path':b'/v1/tenants/a/files',
                'query_string':b'','root_path':'','headers':[(b'authorization',b'Bearer alice'),(b'content-type',b'application/octet-stream'),(b'x-pbk-filename-b64',b'eC5wZGY=')],
                'client':('test',1),'server':('test',80)},receive,send)
            self.assertEqual(sent[0]['status'],400)
        asyncio.run(run())
        self.assertEqual(self.backend.calls,[])
        self.assertEqual(self.upload().status_code,201)

    def test_parallel_roundtrip(self):
        def one(i):
            payload=(str(i).encode()*100_000)[:100_000]
            with TestClient(self.app,raise_server_exceptions=False) as c:
                r=self.upload(f'合同_{i}.pdf',payload,client=c)
                self.assertEqual(r.status_code,201,r.text)
                key=r.json()['key']
                r=c.get(f'/v1/tenants/a/files/{key}',headers={'Authorization':'Bearer alice'})
                self.assertEqual(hashlib.sha256(r.content).digest(),hashlib.sha256(payload).digest())
                return key
        with ThreadPoolExecutor(max_workers=8) as pool:
            keys=list(pool.map(one,range(40)))
        self.assertEqual(len(set(keys)),40)
        self.assertEqual(len(self.backend.objects),40)

    def test_rate_limit_before_body(self):
        gw=TenantGateway(verifier=self.verifier,bindings=[Binding(TenantPolicy('a',Config(max_upload_mb=1),1),'s3/a',self.a)],
            grants=[Grant(Identity('issuer','alice'),'a',frozenset({'upload'}))])
        with TestClient(create_app(gw)) as c:
            self.assertEqual(self.upload(client=c).status_code,201)
            self.assertEqual(self.upload(client=c).status_code,429)
        self.assertEqual(len(self.backend.objects),1)

    def test_capacity_limit(self):
        app=create_app(self.gateway,max_concurrent_uploads=1)
        started, finish=threading.Event(),threading.Event()
        def slow():
            yield b'a'
            started.set()
            if not finish.wait(5): raise RuntimeError('test timeout')
            yield b'b'
        def first():
            with TestClient(app) as c: return self.upload(data=slow(),client=c)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(first)
            try:
                self.assertTrue(started.wait(5))
                with TestClient(app) as c:
                    self.assertEqual(self.upload(client=c).status_code,503)
            finally: finish.set()
            self.assertEqual(future.result(timeout=5).status_code,201)

    def test_real_signed_token_through_http(self):
        import time
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from polyglotblobkit.security import RS256Verifier
        private = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pem = private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        verifier = RS256Verifier(public_key_pem=pem,issuer='issuer',audience='pbk')
        gw=TenantGateway(verifier=verifier,bindings=[Binding(TenantPolicy('a',Config(max_upload_mb=1)),'s3/a',self.a)],
            grants=[Grant(Identity('issuer','alice'),'a',frozenset({'upload'}))])
        now=int(time.time()); claims={'iss':'issuer','aud':'pbk','sub':'alice','iat':now-1,'exp':now+60}
        with TestClient(create_app(gw)) as c:
            token=jwt.encode(claims,private,algorithm='RS256')
            self.assertEqual(self.upload(token=token,client=c).status_code,201)
            expired=jwt.encode(claims|{'exp':now-1},private,algorithm='RS256')
            self.assertEqual(self.upload(token=expired,client=c).status_code,401)
            wrong=jwt.encode(claims|{'aud':'other'},private,algorithm='RS256')
            self.assertEqual(self.upload(token=wrong,client=c).status_code,401)
        self.assertEqual(len(self.backend.objects),1)

    def test_azure_http_contract(self):
        from polyglotblobkit import encode_filename
        from polyglotblobkit.storage import AzureFilenameStorage
        container=Mock(); blob=container.get_blob_client.return_value
        captured={}
        def put(data, **kw): captured.update(data=data.read(), **kw)
        blob.upload_blob.side_effect=put
        body=Mock(spec=['chunks','properties']); body.chunks.return_value=iter([b'abc']);
        body.properties.metadata={METADATA_KEY:encode_filename('合同.pdf')}
        blob.download_blob.return_value=body
        adapter=AzureFilenameStorage(container,max_upload_mb=1)
        gw=TenantGateway(verifier=self.verifier,bindings=[Binding(TenantPolicy('a',Config(max_upload_mb=1)),'azure/a',adapter)],
            grants=[Grant(Identity('issuer','alice'),'a',frozenset({'upload','download'}))])
        with TestClient(create_app(gw)) as c:
            r=self.upload('合同.pdf',b'abc',client=c); self.assertEqual(r.status_code,201)
            self.assertEqual(captured,{'data':b'abc','blob_type':'BlockBlob','metadata':{METADATA_KEY:encode_filename('合同.pdf')},'overwrite':False})
            r=c.get('/v1/tenants/a/files/'+r.json()['key'],headers={'Authorization':'Bearer alice'})
            self.assertEqual(r.content,b'abc')
            self.assertEqual(unquote(r.headers['content-disposition'].split("UTF-8''")[1]),'合同.pdf')

    def test_invalid_utf8_metadata_header(self):
        for value in ('!!!','/w=='):
            self.assertEqual(self.upload(**{'X-PBK-Filename-B64':value}).status_code,400)
        self.assertEqual(self.backend.calls,[])

    def test_session_single_use(self):
        with self.gateway.upload_session('alice','a') as (limit,write):
            self.assertEqual(limit,1_000_000)
            write('x',b'a')
            with self.assertRaises(RuntimeError): write('x',b'b')
        with self.assertRaises(RuntimeError): write('x',b'c')
        self.assertEqual(len(self.backend.objects),1)
