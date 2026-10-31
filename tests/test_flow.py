"""procesar_articulo end to end with every external call mocked."""

import unittest
from unittest import mock

from _env import ba

WP_URL = "https://client.example"
CREDS = {WP_URL: {"wp_user": "bot", "wp_app_password": "xxxx xxxx xxxx xxxx xxxx xxxx"}}
ARTICLE = {
    "id": "page-1",
    "properties": {
        "Artículo": {"title": [{"plain_text": "Dormir mejor"}]},
        "Keyword": {"rich_text": [{"plain_text": "dormir mejor"}]},
        "Enfoque": {"rich_text": [{"plain_text": "práctico"}]},
        "Cliente": {"relation": [{"id": "client-1"}]},
    },
}
LONG_BODY = "<p>" + "palabra " * 1100 + '<a href="https://client.example/">nuestro centro</a></p>'


def make_draft(**overrides):
    draft = {
        "titulo": "Cómo dormir mejor",
        "meta_titulo": "Cómo dormir mejor",
        "meta_descripcion": "Consejos prácticos para dormir mejor.",
        "slug": "dormir-mejor",
        "categoria_sugerida": "Salud",
        "excerpt": "Consejos prácticos.",
        "tags": ["sueño", "descanso"],
        "html": LONG_BODY,
    }
    draft.update(overrides)
    return draft


class FlowHarness(unittest.TestCase):
    """Patches every collaborator; `self.calls` records the order of side effects."""

    wp_url = WP_URL
    cupo = 10
    usados = 0

    def run_flow(self, draft=None, revision_ok=True, count_side_effect=None, tags=([], []), author_id=None):
        self.calls = mock.Mock()
        draft = draft or make_draft()
        self.post = mock.Mock(
            return_value=mock.Mock(status_code=201, text="{}", json=mock.Mock(return_value={"id": 99}))
        )
        patches = {
            "notion_client_fields": mock.Mock(
                return_value={"wp_url": self.wp_url, "cupo": self.cupo, "guia_estilo": "guía"}
            ),
            "notion_count_usados_mes": mock.Mock(
                return_value=self.usados, side_effect=count_side_effect
            ),
            "notion_update_article": self.calls.notion_update_article,
            "avisar_telegram": self.calls.avisar_telegram,
            "wp_fetch_reference_posts": self.calls.wp_fetch_reference_posts,
            "investigar_serp": self.calls.investigar_serp,
            "generar_borrador": self.calls.generar_borrador,
            "revisar_borrador": self.calls.revisar_borrador,
            "wp_fetch_related": mock.Mock(return_value=[]),
            "wp_unique_slug": mock.Mock(side_effect=lambda url, slug, auth: slug),
            "wp_fetch_categories": mock.Mock(return_value={"salud": 3}),
            "wp_resolve_tags": mock.Mock(return_value=tags),
            "wp_ensure_author": mock.Mock(return_value=author_id),
        }
        self.calls.wp_fetch_reference_posts.return_value = []
        self.calls.investigar_serp.return_value = [{"titulo": "t", "url": "https://n.example", "snippet": "", "texto": ""}]
        self.calls.generar_borrador.return_value = draft
        self.calls.revisar_borrador.return_value = {"ok": revision_ok, "html_corregido": draft["html"]}
        with mock.patch.multiple(ba, **patches), mock.patch.object(ba, "DRY_RUN", False), mock.patch.object(
            ba.requests, "post", self.post
        ):
            ba.procesar_articulo(ARTICLE, CREDS)
        return patches

    def notion_states(self):
        return [c.args[1] for c in self.calls.notion_update_article.call_args_list]

    def last_note(self):
        return self.calls.notion_update_article.call_args_list[-1].args[3]

    def posted_body(self):
        self.assertEqual(self.post.call_count, 1)
        return self.post.call_args.kwargs["json"]


class SanitizedPublishTests(FlowHarness):
    def test_clean_draft_is_generado(self):
        self.run_flow()
        self.assertEqual(self.notion_states(), ["En curso", "Generado"])
        body = self.posted_body()
        self.assertEqual(body["status"], "draft")
        self.assertIn('<a href="https://client.example/">nuestro centro</a>', body["content"])
        self.assertNotIn("Saneado", self.last_note())

    def test_malicious_draft_is_sanitized_and_sent_to_revisar(self):
        draft = make_draft(
            titulo='Dormir <img src=x onerror="alert(1)">mejor',
            excerpt="<script>alert(1)</script>Extracto",
            meta_descripcion='"><svg onload=alert(1)>',
            html=LONG_BODY
            + '<script>alert(1)</script><iframe src="https://evil.example"></iframe>'
            + '<p><a href="https://evil.example/">aquí</a> <a href="javascript:alert(1)">y aquí</a></p>',
        )
        self.run_flow(draft=draft)
        self.assertEqual(self.notion_states(), ["En curso", "Revisar"])
        body = self.posted_body()
        for value in (body["content"], body["title"], body["excerpt"], *body["meta"].values()):
            lowered = value.lower()
            for needle in ("<script", "<iframe", "<img", "<svg", "evil.example", "javascript:"):
                self.assertNotIn(needle, lowered)
        self.assertEqual(body["title"], "Dormir mejor")
        self.assertEqual(body["excerpt"], "Extracto")
        self.assertIn("aquí", body["content"])
        note = self.last_note()
        self.assertIn("Saneado", note)
        self.assertIn("script", note)
        aviso = self.calls.avisar_telegram.call_args.args[0]
        self.assertIn("Revisar", aviso)

    def test_wp_publish_draft_sanitizes_even_if_called_with_raw_input(self):
        post = mock.Mock(return_value=mock.Mock(status_code=201, text="{}", json=mock.Mock(return_value={"id": 5})))
        raw = make_draft(html="<p onclick=x>hola</p><script>alert(1)</script>", titulo="<b>T</b>")
        with mock.patch.object(ba, "DRY_RUN", False), mock.patch.object(ba.requests, "post", post):
            link, meta_ok = ba.wp_publish_draft(WP_URL, ("u", "p"), raw)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["content"], "<p>hola</p>")
        self.assertEqual(body["title"], "T")
        self.assertEqual(body["status"], "draft")
        self.assertTrue(meta_ok)
        self.assertEqual(link, f"{WP_URL}/wp-admin/post.php?post=5&action=edit")


class ReliabilityTests(FlowHarness):
    def test_en_curso_is_written_before_any_paid_call(self):
        self.run_flow()
        names = [c[0] for c in self.calls.mock_calls]
        first_update = names.index("notion_update_article")
        self.assertEqual(self.calls.mock_calls[first_update].args[1], "En curso")
        for paid in ("investigar_serp", "generar_borrador", "revisar_borrador"):
            self.assertLess(first_update, names.index(paid))

    def test_quota_check_failure_stops_before_generating(self):
        self.run_flow(count_side_effect=RuntimeError("notion down"))
        self.assertEqual(self.notion_states(), ["Revisar"])
        self.assertIn("cupo", self.last_note_kw())
        self.calls.investigar_serp.assert_not_called()
        self.calls.generar_borrador.assert_not_called()
        self.post.assert_not_called()

    def last_note_kw(self):
        return self.calls.notion_update_article.call_args.kwargs["nota"]

    def test_quota_reached_stops_before_generating(self):
        self.usados = 10
        self.run_flow()
        self.assertEqual(self.notion_states(), ["Revisar"])
        self.calls.generar_borrador.assert_not_called()
        self.post.assert_not_called()

    def test_non_https_client_url_is_refused(self):
        self.wp_url = "http://client.example"
        self.run_flow()
        self.assertEqual(self.notion_states(), ["Revisar"])
        self.calls.generar_borrador.assert_not_called()
        self.post.assert_not_called()

    def test_suggested_tags_go_to_the_note(self):
        self.run_flow(tags=([7], ["tag nueva"]))
        self.assertEqual(self.posted_body()["tags"], [7])
        self.assertIn("tag nueva", self.last_note())

    def test_author_is_only_sent_when_resolved(self):
        self.run_flow(author_id=None)
        self.assertNotIn("author", self.posted_body())
        self.run_flow(author_id=12)
        self.assertEqual(self.posted_body()["author"], 12)


class WordPressHelperTests(unittest.TestCase):
    def _get(self, payload):
        return mock.Mock(return_value=mock.Mock(raise_for_status=mock.Mock(), json=mock.Mock(return_value=payload)))

    def test_tags_are_never_created(self):
        get = self._get([{"id": 4, "name": "Sueño"}, {"id": 5, "name": "Sueño profundo"}])
        post = mock.Mock()
        with mock.patch.object(ba.requests, "get", get), mock.patch.object(ba.requests, "post", post):
            ids, nuevas = ba.wp_resolve_tags(WP_URL, ("u", "p"), ["sueño", "<b>insomnio</b>", "", "sueño"])
        self.assertEqual(ids, [4])
        self.assertEqual(nuevas, ["insomnio"])
        post.assert_not_called()

    def test_author_requires_an_exact_unique_name(self):
        auth = ("u", "p")
        cases = [
            ([{"id": 5, "name": "Client Author"}], 5),
            ([{"id": 6, "name": "Client Author Jr"}, {"id": 7, "name": "client author"}], None),
            ([{"id": 8, "name": "Client Author"}, {"id": 9, "name": "Client Author"}], None),
            ([], None),
        ]
        for users, expected in cases:
            with self.subTest(users=users):
                with mock.patch.object(ba.requests, "get", self._get(users)):
                    self.assertEqual(ba.wp_ensure_author(WP_URL, auth, "Client Author"), expected)

    def test_author_map_matches_the_host_not_a_substring(self):
        self.assertEqual(ba.get_desired_author("https://client.example"), "Client Author")
        self.assertEqual(ba.get_desired_author("https://www.client.example/blog"), "Client Author")
        self.assertEqual(ba.get_desired_author("https://blog.client.example"), "Client Author")
        self.assertIsNone(ba.get_desired_author("https://notclient.example"))
        self.assertIsNone(ba.get_desired_author("https://client.example.evil.example"))
        self.assertIsNone(ba.get_desired_author("not a url"))

    def test_wp_url_must_be_https(self):
        self.assertTrue(ba.wp_url_valida("https://client.example"))
        self.assertTrue(ba.wp_url_valida("https://client.example/blog"))
        for bad in ("http://client.example", "https://u:p@client.example", "https://client.example?x=1",
                    "ftp://client.example", "client.example", "", None, "https://client.example:8080"):
            with self.subTest(url=bad):
                self.assertFalse(ba.wp_url_valida(bad))


if __name__ == "__main__":
    unittest.main()
