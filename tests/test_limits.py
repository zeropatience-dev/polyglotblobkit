import io
import unittest
from unittest.mock import Mock

from blob_filename_fix import UploadSizeLimiter, UploadTooLargeError
from blob_filename_fix.azure import AzureFilenameStorage

MB = 1_000_000


class NonSeekable:
    def __init__(self, data):
        self._stream = io.BytesIO(data)
        self.read_bytes = 0

    def read(self, n):
        result = self._stream.read(n)
        self.read_bytes += len(result)
        return result


class LimiterTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(UploadSizeLimiter().max_bytes, 50 * MB)

    def test_invalid_limits(self):
        for limit in (0, -1, True, 1.5, '10', None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                UploadSizeLimiter(limit)

    def test_bytes_boundaries(self):
        limiter = UploadSizeLimiter(1)
        for size in (0, MB - 1, MB):
            with self.subTest(size=size), limiter.checked(b'x' * size) as payload:
                self.assertEqual(len(payload), size)
        with self.assertRaises(UploadTooLargeError) as ctx:
            with limiter.checked(b'x' * (MB + 1)):
                self.fail('oversized payload accepted')
        self.assertEqual(ctx.exception.limit_bytes, MB)

    def test_mutable_and_view(self):
        for data in (bytearray(b'abc'), memoryview(b'abc')):
            with UploadSizeLimiter(1).checked(data) as payload:
                self.assertEqual(payload, b'abc')
                self.assertIsInstance(payload, bytes)

    def test_nonseekable_exact_limit(self):
        source = NonSeekable(b'x' * MB)
        with UploadSizeLimiter(1).checked(source) as staged:
            self.assertEqual(staged.read(), b'x' * MB)
        self.assertTrue(staged.closed)

    def test_nonseekable_over_limit_stops_reading(self):
        source = NonSeekable(b'x' * (2 * MB))
        with self.assertRaises(UploadTooLargeError):
            with UploadSizeLimiter(1).checked(source):
                self.fail('oversized stream accepted')
        self.assertEqual(source.read_bytes, MB + 1)

    def test_seekable_current_position_and_ownership(self):
        source = io.BytesIO(b'prefixdata')
        source.seek(6)
        with UploadSizeLimiter(1).checked(source) as staged:
            self.assertEqual(staged.read(), b'data')
        self.assertFalse(source.closed)

    def test_invalid_stream(self):
        for source in ('abc', io.StringIO('abc'), object()):
            with self.subTest(source=source), self.assertRaises(TypeError):
                with UploadSizeLimiter(1).checked(source):
                    self.fail('invalid stream accepted')

    def test_staging_above_memory_threshold(self):
        data = b'x' * (2 * MB)
        with UploadSizeLimiter(2).checked(io.BytesIO(data)) as staged:
            self.assertEqual(staged.read(), data)
        self.assertTrue(staged.closed)


class AzureLimiterTests(unittest.TestCase):
    def setUp(self):
        self.container = Mock()
        self.client = self.container.get_blob_client.return_value
        self.storage = AzureFilenameStorage(self.container, max_upload_mb=1)

    def test_over_limit_never_contacts_storage(self):
        for data in (b'x' * (MB + 1), NonSeekable(b'x' * (MB + 1))):
            with self.subTest(data_type=type(data)), self.assertRaises(UploadTooLargeError):
                self.storage.upload('合同.pdf', data)
        self.container.get_blob_client.assert_not_called()

    def test_exact_limit_unicode_upload(self):
        def receive(payload, **kwargs):
            self.assertEqual(payload.read(), b'x' * MB)
            self.assertEqual(kwargs['overwrite'], False)
        self.client.upload_blob.side_effect = receive
        key = self.storage.upload('Müller_合同_😀.pdf', NonSeekable(b'x' * MB))
        self.container.get_blob_client.assert_called_once_with(key)
        self.client.upload_blob.assert_called_once()
        self.assertTrue(self.client.upload_blob.call_args.args[0].closed)

    def test_cleanup_on_storage_error(self):
        self.client.upload_blob.side_effect = RuntimeError('network failure')
        with self.assertRaises(RuntimeError):
            self.storage.upload('x.pdf', io.BytesIO(b'x'))
        self.assertTrue(self.client.upload_blob.call_args.args[0].closed)

    def test_source_error_never_contacts_storage(self):
        source = Mock()
        source.read.side_effect = OSError('read failure')
        with self.assertRaises(OSError):
            self.storage.upload('x.pdf', source)
        self.container.get_blob_client.assert_not_called()
