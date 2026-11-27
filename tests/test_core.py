import unittest
import uuid
from unittest.mock import Mock
from blob_filename_fix import (new_key, validate_key, validate_filename,
    encode_filename, decode_filename, content_disposition, METADATA_KEY)
from blob_filename_fix.azure import AzureFilenameStorage

NAMES = ['Rechnung_Müller.pdf', 'Straße.pdf', '合同.pdf', 'Документ.pdf',
         'ملف.pdf', 'İstanbul.pdf', 'Datei #1 & ? %.pdf', 'Datei_😀.pdf',
         'é.pdf', 'e\u0301.pdf', 'quote".txt']

class CoreTests(unittest.TestCase):
    def test_unicode_roundtrip(self):
        for name in NAMES:
            with self.subTest(name=name):
                encoded = encode_filename(name)
                self.assertTrue(encoded.isascii())
                self.assertEqual(name, decode_filename(encoded))

    def test_no_normalization(self):
        self.assertNotEqual(encode_filename('é.pdf'), encode_filename('e\u0301.pdf'))

    def test_keys(self):
        keys = [new_key() for _ in range(1000)]
        self.assertEqual(len(set(keys)), 1000)
        for key in keys:
            self.assertEqual(validate_key(key), key)
            self.assertEqual(uuid.UUID(key).version, 4)

    def test_invalid_names(self):
        for name in ('', '.', '..', '../x', 'a\\b', 'a\r\nb', 'a\x00b', '😀'*257):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_filename(name)

    def test_invalid_keys(self):
        for key in ('../x', 'A'*32, 'a'*31, 'g'*32):
            with self.assertRaises(ValueError):
                validate_key(key)

    def test_header(self):
        self.assertEqual(content_disposition('合同.pdf'),
            "attachment; filename=\"download\"; filename*=UTF-8''%E5%90%88%E5%90%8C.pdf")
        self.assertIn('%22', content_disposition('quote".txt'))
        self.assertIn('%25', content_disposition('%.txt'))
        for name in NAMES:
            self.assertTrue(content_disposition(name).isascii())

    def test_invalid_metadata(self):
        for value in ('???', '/w=='):
            with self.assertRaises(ValueError):
                decode_filename(value)

class AzureContractTests(unittest.TestCase):
    def setUp(self):
        self.container = Mock()
        self.client = self.container.get_blob_client.return_value
        self.storage = AzureFilenameStorage(self.container)

    def test_upload(self):
        key = self.storage.upload('合同.pdf', b'example')
        self.container.get_blob_client.assert_called_once_with(key)
        self.client.upload_blob.assert_called_once_with(b'example', blob_type='BlockBlob',
            metadata={METADATA_KEY: encode_filename('合同.pdf')}, overwrite=False)

    def test_duplicate_names(self):
        self.assertNotEqual(self.storage.upload('x.pdf', b'1'), self.storage.upload('x.pdf', b'2'))

    def test_download(self):
        downloader = self.client.download_blob.return_value
        downloader.properties.metadata = {METADATA_KEY: encode_filename('ملف.pdf')}
        key = new_key()
        self.assertEqual(self.storage.download(key), ('ملف.pdf', downloader))
        self.container.get_blob_client.assert_called_once_with(key)

    def test_missing_metadata(self):
        self.client.download_blob.return_value.properties.metadata = {}
        with self.assertRaises(ValueError):
            self.storage.download(new_key())

    def test_delete(self):
        key = new_key()
        self.storage.delete(key)
        self.container.get_blob_client.assert_called_once_with(key)
        self.client.delete_blob.assert_called_once_with()

    def test_invalid_key_not_sent(self):
        with self.assertRaises(ValueError):
            self.storage.delete('../x')
        self.container.get_blob_client.assert_not_called()
