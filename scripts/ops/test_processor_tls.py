import importlib.util
from pathlib import Path
import ssl
import unittest
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('processor_tls', ROOT / 'infra/build/processor-postgres-tls.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProcessorTlsTests(unittest.TestCase):
    def dsn(self, mode='verify-full'):
        return 'postgresql://synthetic:encoded%40password@db.invalid:5432/postgres?' + urlencode({
            'sslmode': mode, 'sslrootcert': str(ROOT / 'infra/certs/supabase-root-2021.crt')})

    def test_asyncpg_gets_context_not_unsupported_libpq_keywords(self):
        url, options = module.async_connection_options(self.dsn())
        self.assertEqual(urlsplit(url).scheme, 'postgresql+asyncpg')
        self.assertEqual(urlsplit(url).password, 'encoded%40password')
        self.assertEqual(urlsplit(url).query, '')
        self.assertTrue(options['ssl'].check_hostname)
        self.assertEqual(options['ssl'].verify_mode, ssl.CERT_REQUIRED)
        self.assertNotIn('sslrootcert', options)

    def test_plaintext_fallback_is_rejected(self):
        for mode in ('disable', 'prefer', 'require', 'verify-ca'):
            with self.assertRaises(ValueError):
                module.async_connection_options(self.dsn(mode))

    def test_missing_or_duplicate_tls_options_are_rejected(self):
        for url in ('postgresql://test:local@db.invalid/postgres', self.dsn() + '&sslmode=disable'):
            with self.assertRaises(ValueError):
                module.async_connection_options(url)


if __name__ == '__main__':
    unittest.main()
