import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from polyglotblobkit import Config, Modules, message, resolve_locale, SUPPORTED_LOCALES, UploadTooLargeError
from polyglotblobkit.azure import AzureFilenameStorage
from blob_filename_fix.azure import AzureFilenameStorage as OldAzure
from blob_filename_fix import UploadTooLargeError as OldError

class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(Config.from_dict({}), Config())
        self.assertEqual(Config().max_upload_mb, 50)
    def test_example(self):
        c=Config.load(Path(__file__).resolve().parents[1]/'config.example.json')
        self.assertEqual((c.max_upload_mb,c.locale),(5,'de'))
    def test_partial(self):
        c=Config.from_dict({'modules':{'ui_limiter':False}})
        self.assertEqual(c.modules,Modules(ui_limiter=False))
    def test_reject_invalid(self):
        for data in ([], {'max_upload_mb':0},{'max_upload_mb':True},{'max_upload_mb':9_007_199_255}, {'version':2},{'locale':''},{'modules':None},{'modules':{'ui_limiter':'false'}},{'modules':{'unknown':True}},{'unknown':True}):
            with self.subTest(data=data), self.assertRaises(ValueError): Config.from_dict(data)
    def test_browser_projection(self):
        c=Config(modules=Modules(backend_limiter=False,legacy_support=False))
        self.assertEqual(c.browser_policy(),{'version':1,'max_upload_mb':50,'locale':'en','modules':{'ui_limiter':True}})
    def test_legacy_api_identity(self):
        self.assertIs(AzureFilenameStorage,OldAzure)
        self.assertIs(UploadTooLargeError,OldError)
    def test_configured_limit(self):
        client=Mock();s=AzureFilenameStorage.from_config(client,Config(max_upload_mb=1))
        with self.assertRaises(UploadTooLargeError) as ctx: s.upload('合同.pdf',b'x'*1_000_001)
        self.assertEqual(ctx.exception.code,'UPLOAD_TOO_LARGE')
        client.get_blob_client.assert_not_called()
    def test_ui_disable_does_not_disable_backend(self):
        client=Mock();s=AzureFilenameStorage.from_config(client,Config(max_upload_mb=1,modules=Modules(ui_limiter=False)))
        with self.assertRaises(UploadTooLargeError): s.upload('a.pdf',b'x'*1_000_001)
        client.get_blob_client.assert_not_called()
    def test_disable_backend_requires_explicit_opt_in(self):
        c=Config(max_upload_mb=1,modules=Modules(backend_limiter=False));client=Mock()
        with self.assertRaises(ValueError): AzureFilenameStorage.from_config(client,c)
        s=AzureFilenameStorage.from_config(client,c,allow_unlimited_uploads=True)
        s.upload('x.pdf',b'x'*1_000_001)
        client.get_blob_client.return_value.upload_blob.assert_called_once()
    def test_disable_legacy(self):
        client=Mock();s=AzureFilenameStorage.from_config(client,Config(modules=Modules(legacy_support=False)))
        with self.assertRaises(ValueError):s.download_legacy('old.pdf')
        client.get_blob_client.assert_not_called()

class I18nTests(unittest.TestCase):
    def test_all_languages(self):
        self.assertEqual(set(SUPPORTED_LOCALES),set('en de fr es tr zh ja ar'.split()))
        for lang in SUPPORTED_LOCALES:
            with self.subTest(lang=lang):
                text=message('UPLOAD_TOO_LARGE',lang,limit=5)
                self.assertIn('5',text);self.assertNotIn('{limit}',text)
                self.assertTrue(message('ACCEPTED',lang))
    def test_fallback(self):
        self.assertEqual(resolve_locale('de-DE'),'de')
        self.assertEqual(resolve_locale('zh_CN'),'zh')
        self.assertEqual(resolve_locale('xx'),'en')
        self.assertEqual(resolve_locale('ar-SA'),'ar')
    def test_error_parameters(self):
        with self.assertRaises(ValueError):message('UPLOAD_TOO_LARGE','de')
        with self.assertRaises(KeyError):message('unknown','de')
    def test_catalog_consistency(self):
        catalog=json.loads((Path(__file__).resolve().parents[1]/'blob_filename_fix/messages.json').read_text())
        for translations in catalog.values():
            self.assertEqual(set(translations),set(catalog['en']))
            self.assertEqual(translations['UPLOAD_TOO_LARGE'].count('{limit}'),1)
