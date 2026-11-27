import io
import unittest
from unittest.mock import Mock, patch
from polyglotblobkit import (Config, Modules, METADATA_KEY, encode_filename,
    UploadTooLargeError, new_key)
from polyglotblobkit.storage import S3FilenameStorage, MinioFilenameStorage, open_download, AzureFilenameStorage
from polyglotblobkit.security import TenantGateway, TenantPolicy, Binding, Grant, Identity, AccessDenied


class Body(io.BytesIO):
    def iter_chunks(self, chunk_size=65536):
        return iter(lambda: self.read(chunk_size), b'')


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.calls = []
        self.last_body = None
    def put_object(self, **kw):
        self.calls.append(('put', kw['Bucket'], kw['Key']))
        k = (kw['Bucket'], kw['Key'])
        if kw['IfNoneMatch'] != '*' or k in self.objects:
            raise RuntimeError('Conditional write failed')
        self.objects[k] = (dict(kw['Metadata']), kw['Body'] if isinstance(kw['Body'], bytes) else kw['Body'].read())
    def get_object(self, Bucket, Key):
        self.calls.append(('get', Bucket, Key))
        metadata, data = self.objects[Bucket, Key]
        self.last_body = Body(data)
        return {'Metadata': metadata, 'Body': self.last_body}
    def delete_object(self, Bucket, Key):
        self.calls.append(('delete', Bucket, Key))
        self.objects.pop((Bucket, Key), None)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeS3()
        self.s = S3FilenameStorage(self.client, 'tenant-a', max_upload_mb=1)
    def test_roundtrip_both_providers(self):
        for adapter in (S3FilenameStorage, MinioFilenameStorage):
            s = adapter(self.client, 'tenant-a')
            for name in ['Müller.pdf','合同.pdf','ملف.pdf','😀 #%.pdf','e\u0301.pdf','é.pdf','İstanbul.pdf']:
                with self.subTest(adapter=adapter, name=name):
                    key = s.upload(name, io.BytesIO(b'abc'))
                    with open_download(s, key) as (filename, chunks):
                        self.assertEqual((filename,b''.join(chunks)), (name,b'abc'))
                    self.assertTrue(self.client.last_body.closed)
                    s.delete(key)
                    self.assertNotIn(('tenant-a',key), self.client.objects)
    def test_distinct_names_and_unicode_forms(self):
        keys = [self.s.upload(n,b'x') for n in ['é','e\u0301','é']]
        self.assertEqual(len(set(keys)),3)
    def test_exact_limit(self):
        self.s.upload('x',io.BytesIO(b'x'*1_000_000))
        self.assertEqual(len(self.client.calls),1)
    def test_over_limit_no_write(self):
        for data in (b'x'*1_000_001,io.BytesIO(b'x'*1_000_001)):
            with self.assertRaises(UploadTooLargeError): self.s.upload('x',data)
        self.assertEqual(self.client.calls,[])
    def test_invalid_name_key_no_access(self):
        with self.assertRaises(ValueError): self.s.upload('../x',b'x')
        with self.assertRaises(ValueError): self.s.download('../x')
        with self.assertRaises(ValueError): self.s.delete('../x')
        self.assertEqual(self.client.calls,[])
    def test_collision_never_overwrites(self):
        with patch('polyglotblobkit.storage.s3.new_key',return_value=new_key()):
            key=self.s.upload('first',b'first')
            with self.assertRaises(RuntimeError): self.s.upload('second',b'second')
        with open_download(self.s,key) as (name,chunks): self.assertEqual((name,b''.join(chunks)),('first',b'first'))
    def test_metadata_missing_closes_body(self):
        key=new_key(); self.client.objects['tenant-a',key]=({},b'x')
        with self.assertRaises(ValueError): self.s.download(key)
        self.assertTrue(self.client.last_body.closed)
    def test_metadata_invalid_closes_body(self):
        key=new_key(); self.client.objects['tenant-a',key]=({METADATA_KEY:'!!!'},b'x')
        with self.assertRaises(ValueError): self.s.download(key)
        self.assertTrue(self.client.last_body.closed)
    def test_legacy_exact_name(self):
        name='prefix/合同 #%.pdf'; self.client.objects['tenant-a',name]=({},b'legacy')
        original,body=self.s.download_legacy(name)
        with body: self.assertEqual((original,body.read()),('合同 #%.pdf',b'legacy'))
        self.assertEqual(self.client.calls[-1],('get','tenant-a',name))
    def test_legacy_disabled(self):
        s=S3FilenameStorage.from_config(self.client,'tenant-a',Config(modules=Modules(legacy_support=False)))
        with self.assertRaises(ValueError): s.download_legacy('x')
        self.assertEqual(self.client.calls,[])
    def test_limit_cannot_disable(self):
        with self.assertRaises(ValueError): S3FilenameStorage.from_config(self.client,'tenant-a',Config(modules=Modules(backend_limiter=False)),allow_unlimited_uploads=True)
    def test_single_put_ceiling(self):
        with self.assertRaises(ValueError): S3FilenameStorage(self.client,'tenant-a',max_upload_mb=5001)
    def test_early_exit_closes_body(self):
        k=self.s.upload('x',b'x')
        with self.assertRaises(RuntimeError):
            with open_download(self.s,k): raise RuntimeError('client disconnected')
        self.assertTrue(self.client.last_body.closed)
    def test_azure_stream_contract(self):
        azure = Mock(spec=AzureFilenameStorage)
        body=Mock(spec=['chunks']); body.chunks.return_value=iter([b'a',b'b'])
        azure.download.return_value=('合同.pdf',body)
        with open_download(azure,new_key()) as (name,chunks): self.assertEqual((name,b''.join(chunks)),('合同.pdf',b'ab'))
    def test_tenant_isolation(self):
        b=MinioFilenameStorage(self.client,'tenant-b',max_upload_mb=2)
        verifier=Mock(); verifier.verify.side_effect=lambda t:Identity('issuer',t)
        gateway=TenantGateway(verifier=verifier,bindings=[Binding(TenantPolicy('a',Config(max_upload_mb=1)),'s3/tenant-a',self.s),Binding(TenantPolicy('b',Config(max_upload_mb=2)),'s3/tenant-b',b)],grants=[Grant(Identity('issuer','alice'),'a',frozenset({'upload','download'})),Grant(Identity('issuer','bob'),'b',frozenset({'upload','download'}))])
        key=gateway.upload('bob','b','秘密.pdf',b'x')
        with self.assertRaises(AccessDenied): gateway.download('alice','b',key)
        with self.assertRaises(KeyError): gateway.download('alice','a',key)
        with self.assertRaises(UploadTooLargeError): gateway.upload('alice','a','x',b'x'*1_000_001)
        self.assertEqual(self.client.calls,[('put','tenant-b',key),('get','tenant-a',key)])


@unittest.skipUnless(__import__("importlib.util", fromlist=["find_spec"]).find_spec("boto3"), "Optional boto3 SDK not installed")
class SDKContractTests(unittest.TestCase):
    def setUp(self):
        import boto3
        from botocore.stub import Stubber
        self.client=boto3.client('s3',region_name='us-east-1',aws_access_key_id='test',aws_secret_access_key='test')
        self.addCleanup(self.client.close)
        self.stub=Stubber(self.client); self.stub.activate(); self.addCleanup(self.stub.deactivate)
        self.s=S3FilenameStorage(self.client,'tenant-a')
    def test_sdk_put_and_delete_parameters(self):
        key=new_key()
        self.stub.add_response('put_object',{}, {'Bucket':'tenant-a','Key':key,'Body':b'x','Metadata':{METADATA_KEY:encode_filename('合同.pdf')},'IfNoneMatch':'*','ContentType':'application/octet-stream'})
        self.stub.add_response('delete_object',{}, {'Bucket':'tenant-a','Key':key})
        with patch('polyglotblobkit.storage.s3.new_key',return_value=key): self.assertEqual(self.s.upload('合同.pdf',b'x'),key)
        self.s.delete(key); self.stub.assert_no_pending_responses()
    def test_sdk_collision_is_not_retried_unconditionally(self):
        from botocore.exceptions import ClientError
        key=new_key()
        self.stub.add_client_error('put_object','PreconditionFailed',http_status_code=412,expected_params={'Bucket':'tenant-a','Key':key,'Body':b'x','Metadata':{METADATA_KEY:encode_filename('x')},'IfNoneMatch':'*','ContentType':'application/octet-stream'})
        with patch('polyglotblobkit.storage.s3.new_key',return_value=key),self.assertRaises(ClientError): self.s.upload('x',b'x')
        self.stub.assert_no_pending_responses()
