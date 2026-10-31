"""Secret leaks: redaction helper, Telegram notifier and error paths."""

import json
import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

import requests

from _env import OPENAI_KEY, TELEGRAM_TOKEN, ba

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
LEAKY_ERROR = requests.ConnectionError(
    f"HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded with url: "
    f"/bot{TELEGRAM_TOKEN}/sendMessage (Caused by NameResolutionError)"
)


class RedactionTests(unittest.TestCase):
    def test_patterns(self):
        cases = {
            f"GET {TELEGRAM_URL}": TELEGRAM_TOKEN,
            "url /bot987654:XYZ_abc-123/getMe": "987654:XYZ_abc-123",
            "Authorization: Bearer abc.def-ghi_123": "abc.def-ghi_123",
            "Authorization: Basic dXNlcjpwYXNzd29yZA==": "dXNlcjpwYXNzd29yZA==",
            "key sk-proj-AbCdEf0123456789 here": "sk-proj-AbCdEf0123456789",
            "notion secret_AbCdEfGhIjKlMnOpQrSt": "secret_AbCdEfGhIjKlMnOpQrSt",
            "notion ntn_AbCdEfGhIjKlMnOpQrSt": "ntn_AbCdEfGhIjKlMnOpQrSt",
            "https://x.example/?api_key=SuperSecret1&q=1": "SuperSecret1",
            "{'X-API-KEY': 'serper-raw-value'}": "serper-raw-value",
            "password=hunter2hunter2": "hunter2hunter2",
        }
        for text, secret in cases.items():
            with self.subTest(text=text):
                redacted = ba.redactar_secretos(text)
                self.assertNotIn(secret, redacted)
                self.assertIn("<redactado>", redacted)

    def test_configured_secrets_are_redacted_literally(self):
        self.assertNotIn("serper-test-key-0123456789", ba.redactar_secretos("k=serper-test-key-0123456789 x"))
        self.assertNotIn(OPENAI_KEY, ba.redactar_secretos(f"key {OPENAI_KEY}"))
        self.assertEqual(ba.redactar_secretos(None), "")
        self.assertEqual(ba.redactar_secretos("texto normal sin secretos"), "texto normal sin secretos")

    def test_wp_app_passwords_are_registered_when_loading_credentials(self):
        creds = {"https://client.example": {"wp_user": "bot", "wp_app_password": "abcd EFGH ijkl MNOP qrst UVWX"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wp_credentials.json")
            with open(path, "w") as f:
                json.dump(creds, f)
            with mock.patch.object(ba, "WP_CREDENTIALS_FILE", path):
                self.assertEqual(ba.load_wp_credentials(), creds)
        redacted = ba.redactar_secretos("auth failed for abcd EFGH ijkl MNOP qrst UVWX / abcdEFGHijklMNOPqrstUVWX")
        self.assertNotIn("abcd EFGH", redacted)
        self.assertNotIn("abcdEFGH", redacted)

    def test_log_formatter_redacts_messages_and_tracebacks(self):
        formatter = ba.FormateadorRedactado("%(levelname)s %(message)s")
        try:
            raise LEAKY_ERROR
        except requests.ConnectionError:
            record = logging.LogRecord("t", logging.ERROR, __file__, 1, "fallo %s", (TELEGRAM_URL,), sys.exc_info())
        output = formatter.format(record)
        self.assertNotIn(TELEGRAM_TOKEN, output)
        self.assertIn("ConnectionError", output)

    def test_logging_is_wired_through_the_redacting_formatter(self):
        self.assertIsInstance(ba._log_handler.formatter, ba.FormateadorRedactado)


class TelegramTests(unittest.TestCase):
    def test_network_error_is_swallowed_and_only_the_type_is_logged(self):
        with mock.patch.object(ba.requests, "post", side_effect=LEAKY_ERROR):
            with self.assertLogs(ba.log, level="WARNING") as logs:
                self.assertFalse(ba.avisar_telegram("hola"))
        joined = "\n".join(logs.output)
        self.assertIn("ConnectionError", joined)
        self.assertNotIn(TELEGRAM_TOKEN, joined)
        self.assertNotIn("api.telegram.org", joined)

    def test_non_200_is_reported_without_raising(self):
        with mock.patch.object(ba.requests, "post", return_value=mock.Mock(status_code=401)):
            with self.assertLogs(ba.log, level="WARNING"):
                self.assertFalse(ba.avisar_telegram("hola"))

    def test_outgoing_text_is_redacted(self):
        post = mock.Mock(return_value=mock.Mock(status_code=200))
        with mock.patch.object(ba.requests, "post", post):
            self.assertTrue(ba.avisar_telegram(f"fallo con {TELEGRAM_URL} y {OPENAI_KEY}"))
        sent = post.call_args.kwargs["json"]["text"]
        self.assertNotIn(TELEGRAM_TOKEN, sent)
        self.assertNotIn(OPENAI_KEY, sent)


class ErrorPathTests(unittest.TestCase):
    def test_notion_note_is_redacted(self):
        patch = mock.Mock(return_value=mock.Mock(raise_for_status=mock.Mock()))
        with mock.patch.object(ba.requests, "patch", patch):
            ba.notion_update_article("page", "Revisar", nota=f"Error {TELEGRAM_URL}")
        content = patch.call_args.kwargs["json"]["properties"]["Nota"]["rich_text"][0]["text"]["content"]
        self.assertNotIn(TELEGRAM_TOKEN, content)

    def test_main_never_sends_exception_text_to_notion_or_telegram(self):
        update = mock.Mock()
        telegram = mock.Mock(return_value=True)
        with mock.patch.multiple(
            ba,
            acquire_lock=mock.Mock(return_value=True),
            load_wp_credentials=mock.Mock(return_value={}),
            notion_get_pending_articles=mock.Mock(return_value=[{"id": "page-1"}]),
            procesar_articulo=mock.Mock(side_effect=LEAKY_ERROR),
            notion_update_article=update,
            avisar_telegram=telegram,
        ):
            with self.assertLogs(ba.log, level="ERROR"):
                ba.main()
        nota = update.call_args.kwargs["nota"]
        self.assertEqual(update.call_args.args[:2], ("page-1", "Revisar"))
        self.assertIn("ConnectionError", nota)
        aviso = telegram.call_args.args[0]
        self.assertIn("ConnectionError", aviso)
        for text in (nota, aviso):
            self.assertNotIn(TELEGRAM_TOKEN, text)
            self.assertNotIn("api.telegram.org", text)
            self.assertNotIn("Max retries", text)

    def test_main_survives_notion_failure_in_the_error_path(self):
        with mock.patch.multiple(
            ba,
            acquire_lock=mock.Mock(return_value=True),
            load_wp_credentials=mock.Mock(return_value={}),
            notion_get_pending_articles=mock.Mock(return_value=[{"id": "p1"}, {"id": "p2"}]),
            procesar_articulo=mock.Mock(side_effect=RuntimeError("x")),
            notion_update_article=mock.Mock(side_effect=LEAKY_ERROR),
            avisar_telegram=mock.Mock(return_value=False),
        ):
            with self.assertLogs(ba.log, level="WARNING"):
                ba.main()
            self.assertEqual(ba.procesar_articulo.call_count, 2)


if __name__ == "__main__":
    unittest.main()
