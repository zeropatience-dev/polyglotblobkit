"""Opt-in live S3/MinIO tests. Use a dedicated, non-production bucket."""
import os
import io
import unittest
from unittest.mock import patch
from polyglotblobkit import UploadTooLargeError
from polyglotblobkit.storage import S3FilenameStorage, MinioFilenameStorage, open_download


@unittest.skipUnless(os.environ.get('PBK_TEST_S3_BUCKET'), 'Dedicated S3 test bucket not configured')
class S3IntegrationTests(unittest.TestCase):
    def setUp(self):
        import boto3
        from botocore.config import Config
        endpoint = os.environ.get('PBK_TEST_S3_ENDPOINT') or None
        self.client = boto3.client('s3', endpoint_url=endpoint,
            config=Config(s3={'addressing_style': 'path' if endpoint else 'auto'}))
        self.addCleanup(self.client.close)
        self.bucket = os.environ['PBK_TEST_S3_BUCKET']
        cls = MinioFilenameStorage if endpoint else S3FilenameStorage
        self.storage = cls(self.client, self.bucket, max_upload_mb=1)

    def test_unicode_and_conditional_write(self):
        from botocore.exceptions import ClientError
        name = 'Müller_合同_ملف_e\u0301.pdf'
        key = self.storage.upload(name, io.BytesIO(b'original'))
        self.addCleanup(self.storage.delete, key)
        with patch('polyglotblobkit.storage.s3.new_key', return_value=key):
            with self.assertRaises(ClientError) as err:
                self.storage.upload('other.pdf', b'other')
            self.assertIn(err.exception.response['ResponseMetadata']['HTTPStatusCode'], (409, 412))
        with open_download(self.storage, key) as (actual, chunks):
            self.assertEqual((actual, b''.join(chunks)), (name, b'original'))

    def test_limit(self):
        with self.assertRaises(UploadTooLargeError):
            self.storage.upload('large.pdf', io.BytesIO(b'x' * 1_000_001))
