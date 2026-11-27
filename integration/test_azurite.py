"""Run against a dedicated test account/emulator; creates and deletes its own container."""
import os
import unittest
import uuid
import io
from blob_filename_fix import UploadTooLargeError
from blob_filename_fix.azure import AzureFilenameStorage

class AzuriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from azure.storage.blob import BlobServiceClient
        connection = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        if not connection:
            raise RuntimeError('AZURE_STORAGE_CONNECTION_STRING is required for integration tests')
        cls.service = BlobServiceClient.from_connection_string(connection)
        cls.addClassCleanup(cls.service.close)
        cls.container = cls.service.create_container('test-' + uuid.uuid4().hex)
        cls.addClassCleanup(cls.container.delete_container)
        cls.storage = AzureFilenameStorage(cls.container, max_upload_mb=5)

    def test_unicode_roundtrip_and_delete(self):
        for name in ['Müller.pdf','合同.pdf','ملف.pdf','e\u0301_😀 #%.pdf']:
            with self.subTest(name=name):
                key = self.storage.upload(name,b'payload')
                original, data = self.storage.download(key)
                self.assertEqual((original,data.readall()),(name,b'payload'))
                self.storage.delete(key)
                self.assertFalse(self.container.get_blob_client(key).exists())

    def test_legacy_exact_name(self):
        name = 'tenant/合同 #%.pdf'
        client = self.container.get_blob_client(name)
        client.upload_blob(b'legacy',overwrite=False)
        original,data = self.storage.download_legacy(name)
        self.assertEqual((original,data.readall()),('合同 #%.pdf',b'legacy'))
        self.assertTrue(client.exists())

    def test_limit(self):
        key = self.storage.upload('exact.pdf',io.BytesIO(b'x'*5_000_000))
        self.assertEqual(self.container.get_blob_client(key).get_blob_properties().size,5_000_000)
        before = {b.name for b in self.container.list_blobs()}
        with self.assertRaises(UploadTooLargeError):
            self.storage.upload('large.pdf',io.BytesIO(b'x'*5_000_001))
        self.assertEqual(before,{b.name for b in self.container.list_blobs()})
