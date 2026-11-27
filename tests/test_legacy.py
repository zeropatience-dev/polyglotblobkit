import unittest
from unittest.mock import Mock
from blob_filename_fix import METADATA_KEY, encode_filename
from blob_filename_fix.azure import AzureFilenameStorage

class LegacyTests(unittest.TestCase):
    def setUp(self):
        self.container = Mock()
        self.downloader = self.container.get_blob_client.return_value.download_blob.return_value
        self.downloader.properties.metadata = {}
        self.storage = AzureFilenameStorage(self.container)

    def test_exact_legacy_name(self):
        key = 'tenant/2026/e\u0301_合同 #%.pdf'
        self.assertEqual(self.storage.download_legacy(key), ('e\u0301_合同 #%.pdf', self.downloader))
        self.container.get_blob_client.assert_called_once_with(key)

    def test_explicit_name(self):
        self.assertEqual(self.storage.download_legacy('some/opaque/key', original_filename='Straße.pdf')[0], 'Straße.pdf')

    def test_metadata(self):
        self.downloader.properties.metadata = {METADATA_KEY: encode_filename('ملف.pdf')}
        self.assertEqual(self.storage.download_legacy('old-id')[0], 'ملف.pdf')

    def test_no_silent_fallback_for_corrupt_metadata(self):
        self.downloader.properties.metadata = {METADATA_KEY: '???'}
        with self.assertRaises(ValueError): self.storage.download_legacy('old.pdf')

    def test_invalid_explicit_name_before_remote_call(self):
        with self.assertRaises(ValueError): self.storage.download_legacy('old.pdf', original_filename='../x')
        self.container.get_blob_client.assert_not_called()

    def test_empty_key(self):
        with self.assertRaises(ValueError): self.storage.download_legacy('')
        self.container.get_blob_client.assert_not_called()

    def test_legacy_with_trailing_slash_requires_explicit_name(self):
        with self.assertRaises(ValueError): self.storage.download_legacy('old/')
        self.assertEqual(self.storage.download_legacy('old/', original_filename='old.pdf')[0], 'old.pdf')
