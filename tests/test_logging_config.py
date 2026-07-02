import unittest
from unittest.mock import patch

from rag.logging_config import configure_sentry


class TestConfigureSentry(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("rag.logging_config.sentry_sdk.init")
    def test_ne_configure_rien_sans_dsn(self, mock_init):
        configure_sentry()
        mock_init.assert_not_called()

    @patch.dict("os.environ", {"SENTRY_DSN": "https://example.test/1"})
    @patch("rag.logging_config.sentry_sdk.init")
    def test_configure_sans_variables_locales_avec_dsn(self, mock_init):
        configure_sentry()
        mock_init.assert_called_once_with(
            dsn="https://example.test/1", include_local_variables=False
        )
