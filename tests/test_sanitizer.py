"""Stored XSS: allowlist sanitizer applied to the model output before posting."""

import re
import unittest
from html.parser import HTMLParser
from unittest import mock

from _env import ba

DOMAIN = "client.example"
WP_URL = "https://client.example"

# Payloads that must never survive as markup. Several are only meaningful for
# a browser (mXSS, broken tags); the property checked is the same for all.
NASTY = [
    "<script>alert(1)</script>",
    "<SCRIPT SRC=https://evil.example/x.js></SCRIPT>",
    "<img src=x onerror=alert(1)>",
    '<p onclick="alert(1)">x</p>',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="jav&#x61;script:alert(1)">x</a>',
    '<a href=" javascript:alert(1)">x</a>',
    '<a href="java\nscript:alert(1)">x</a>',
    '<a href="JaVaScRiPt:alert(1)">x</a>',
    '<a href="https://evil.example/">x</a>',
    '<a href="//evil.example/">x</a>',
    '<a href="https://client.example.evil.example/">x</a>',
    '<a href="https://client.example@evil.example/">x</a>',
    '<a href="https://client.example/" onmouseover="alert(1)">x</a>',
    '<a href="https://client.example/&quot;onmouseover=alert(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    '<iframe src="https://evil.example"></iframe>',
    "<svg><script>alert(1)</script></svg>",
    "<svg onload=alert(1)>",
    "<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>",
    "<style>body{background:url(javascript:alert(1))}</style>",
    "<!--<script>alert(1)</script>-->",
    "<![CDATA[<script>alert(1)</script>]]>",
    "<scr<script>ipt>alert(1)</script>",
    "<<script>alert(1)//<</script>",
    "<p>unclosed <strong>tags <em>everywhere",
    "</p></strong></a></ul>stray closers",
    "<script>alert(1)",
    '<noscript><p title="</noscript><img src=x onerror=alert(1)>">',
    "<form><button formaction=javascript:alert(1)>x</button></form>",
    '<object data="javascript:alert(1)"></object>',
    '<embed src="javascript:alert(1)">',
    '<base href="https://evil.example/">',
    '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    "<link rel=stylesheet href=https://evil.example/x.css>",
    "<details open ontoggle=alert(1)>",
    '<a href="https://client.example/ok"><a href="https://client.example/nested">n</a></a>',
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "&#60;img src=x onerror=alert(1)&#62;",
    "<p>a</p><![if !IE]><script>alert(1)</script><![endif]>",
    "<p>\x00<scr\x00ipt>alert(1)</script></p>",
    "<textarea><script>alert(1)</script></textarea>",
    "<title><script>alert(1)</script></title>",
    "<template><script>alert(1)</script></template>",
    "<![foo[ bar",
    "<p>x</p><!DOCTYPE html><?php echo 1; ?>",
]


class _Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.other = 0

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_comment(self, data):
        self.other += 1

    handle_decl = handle_pi = unknown_decl = handle_comment


def sanitize(markup):
    return ba.sanear_html(markup, DOMAIN)


class SafeOutputMixin:
    def assertSafe(self, output):
        inspector = _Inspector()
        inspector.feed(output)
        inspector.close()
        self.assertEqual(inspector.other, 0, output)
        for tag, attrs in inspector.tags:
            self.assertIn(tag, ba.ETIQUETAS_PERMITIDAS, output)
            if tag == "a":
                self.assertEqual([name for name, _ in attrs], ["href"], output)
                self.assertTrue(ba.href_permitido(attrs[0][1], DOMAIN), output)
            else:
                self.assertEqual(attrs, [], output)
        # Every "<" left in the output opens or closes an allowed tag.
        for name in re.findall(r"<\s*/?\s*([^\s>/]*)", output):
            self.assertIn(name.lower(), ba.ETIQUETAS_PERMITIDAS, output)


class SanitizerPropertyTests(SafeOutputMixin, unittest.TestCase):
    def test_nasty_payloads_never_survive(self):
        for payload in NASTY:
            with self.subTest(payload=payload):
                output, _ = sanitize(payload)
                self.assertSafe(output)

    def test_sanitizer_is_idempotent(self):
        for payload in NASTY + ["<p>Hola <strong>mundo</strong> &amp; <a href='https://client.example/x'>x</a></p>"]:
            with self.subTest(payload=payload):
                once, _ = sanitize(payload)
                twice, informe = sanitize(once)
                self.assertEqual(once, twice)
                self.assertEqual(ba.resumen_saneado(informe), "")


class SanitizerBehaviourTests(SafeOutputMixin, unittest.TestCase):
    def test_script_is_removed_with_its_content(self):
        output, informe = sanitize("<p>Hola</p><script>alert(1)</script><p>adiós</p>")
        self.assertEqual(output, "<p>Hola</p> <p>adiós</p>")
        self.assertEqual(informe["etiquetas"], {"script": 1})
        self.assertNotEqual(ba.resumen_saneado(informe), "")

    def test_img_onerror_is_removed(self):
        output, informe = sanitize("<p>Foto <img src=x onerror=alert(1)> aquí</p>")
        self.assertNotIn("<img", output)
        self.assertNotIn("onerror", output)
        self.assertIn("Foto", output)
        self.assertIn("aquí", output)
        self.assertEqual(informe["etiquetas"], {"img": 1})

    def test_javascript_hrefs_are_unwrapped_to_text(self):
        for href in ("javascript:alert(1)", "jav&#x61;script:alert(1)", " JAVASCRIPT:alert(1)", "java\tscript:x"):
            with self.subTest(href=href):
                output, informe = sanitize(f'<p><a href="{href}">pulsa</a></p>')
                self.assertEqual(output, "<p>pulsa</p>")
                self.assertEqual(informe["enlaces"], 1)

    def test_external_and_non_https_links_are_unwrapped(self):
        for href in (
            "https://evil.example/",
            "http://client.example/",
            "//client.example/",
            "/relative",
            "#anchor",
            "https://client.example.evil.example/",
            "https://user@client.example/",
            "https://client.example:8443/",
            "https://client.example\\@evil.example/",
        ):
            with self.subTest(href=href):
                output, informe = sanitize(f'<a href="{href}">texto</a>')
                self.assertEqual(output, "texto")
                self.assertEqual(informe["enlaces"], 1)

    def test_own_domain_https_links_are_kept(self):
        for href in ("https://client.example/", "https://www.client.example/blog/post", "HTTPS://Client.Example/x"):
            with self.subTest(href=href):
                output, informe = sanitize(f'<a href="{href}">texto</a>')
                self.assertEqual(output, f'<a href="{href}">texto</a>')
                self.assertEqual(ba.resumen_saneado(informe), "")

    def test_attributes_are_dropped_and_href_is_escaped(self):
        output, informe = sanitize('<p class="x" style="color:red">t</p>')
        self.assertEqual(output, "<p>t</p>")
        self.assertEqual(informe["atributos"], 2)

        output, informe = sanitize(
            '<a title="x" href="https://client.example/?a=1&amp;b=&quot;x" onclick="alert(1)">t</a>'
        )
        self.assertEqual(output, '<a href="https://client.example/?a=1&amp;b=&quot;x">t</a>')
        self.assertEqual(informe["atributos"], 2)

    def test_nested_and_unclosed_tags_are_balanced(self):
        output, _ = sanitize("<p>uno <strong>dos <em>tres</p><p>cuatro")
        self.assertEqual(output, "<p>uno <strong>dos <em>tres</em></strong></p><p>cuatro</p>")
        output, _ = sanitize("<ul><li>a<li>b</ul>")
        self.assertEqual(output, "<ul><li>a</li><li>b</li></ul>")
        output, _ = sanitize("<p>intro<ul><li>x</li></ul>")
        self.assertEqual(output, "<p>intro</p><ul><li>x</li></ul>")
        output, _ = sanitize("</p></strong>texto")
        self.assertEqual(output, "texto")

    def test_nested_links_are_not_nested(self):
        output, informe = sanitize(
            '<a href="https://client.example/a">uno <a href="https://client.example/b">dos</a></a>'
        )
        self.assertEqual(output, '<a href="https://client.example/a">uno dos</a>')
        self.assertEqual(informe["otros"], 1)

    def test_entities_stay_text(self):
        output, informe = sanitize("<p>&lt;script&gt;alert(1)&lt;/script&gt; &amp; &aacute; &#60;b&#62;</p>")
        self.assertEqual(output, "<p>&lt;script&gt;alert(1)&lt;/script&gt; &amp; á &lt;b&gt;</p>")
        self.assertEqual(ba.resumen_saneado(informe), "")

    def test_h1_is_dropped_silently(self):
        output, informe = sanitize("<h1>Título</h1><p>Cuerpo</p>")
        self.assertEqual(output, "<p>Cuerpo</p>")
        self.assertEqual(informe["h1"], 1)
        self.assertEqual(ba.resumen_saneado(informe), "")
        output, _ = sanitize("<h1>Título sin cerrar<p>Cuerpo</p>")
        self.assertEqual(output, "<p>Cuerpo</p>")

    def test_comments_and_declarations_are_flagged(self):
        output, informe = sanitize("<!-- wp:paragraph --><p>x</p><!DOCTYPE html>")
        self.assertEqual(output, "<p>x</p>")
        self.assertEqual(informe["otros"], 2)

    def test_unclosed_script_drops_everything_after_it(self):
        output, informe = sanitize("<p>antes</p><script>alert(1)<p>después</p>")
        self.assertEqual(output, "<p>antes</p>")
        self.assertEqual(informe["etiquetas"], {"script": 1})

    def test_parser_failure_falls_back_to_escaped_text(self):
        with mock.patch.object(ba._Saneador, "feed", side_effect=ValueError("boom")):
            output, informe = sanitize("<p onclick=x>hola</p>")
        self.assertEqual(output, "<p>&lt;p onclick=x&gt;hola&lt;/p&gt;</p>")
        self.assertNotEqual(ba.resumen_saneado(informe), "")
        self.assertSafe(output)


class PlainTextFieldTests(unittest.TestCase):
    def test_tags_and_angle_brackets_are_removed(self):
        self.assertEqual(ba.texto_plano("<b>Hola</b> <script>x()</script>mundo", 100), "Hola mundo")
        self.assertEqual(ba.texto_plano("a &lt;script&gt; b", 100), "a script b")
        self.assertEqual(ba.texto_plano('"><img src=x onerror=alert(1)>', 100), '"')

    def test_entities_whitespace_and_control_chars(self):
        self.assertEqual(ba.texto_plano("  Sal &amp; pimienta \n\t", 100), "Sal & pimienta")
        self.assertEqual(ba.texto_plano("a\x00b​c\x1b", 100), "abc")

    def test_length_is_capped_on_a_word_boundary(self):
        value = ba.texto_plano("palabra " * 50, 30)
        self.assertLessEqual(len(value), 30)
        self.assertTrue(value.endswith("palabra"))
        self.assertEqual(ba.texto_plano("x" * 50, 10), "x" * 10)

    def test_sanear_borrador_flags_only_real_changes(self):
        clean = {
            "titulo": "Cómo dormir mejor &amp; descansar",
            "meta_titulo": "Dormir mejor",
            "meta_descripcion": "Guía práctica.",
            "excerpt": "Un  extracto\ncon espacios.",
            "html": "<p>Hola</p>",
            "slug": "dormir-mejor",
        }
        limpio, informe = ba.sanear_borrador(clean, WP_URL)
        self.assertEqual(informe["campos"], [])
        self.assertEqual(limpio["titulo"], "Cómo dormir mejor & descansar")
        self.assertEqual(limpio["slug"], "dormir-mejor")

        dirty = dict(clean, titulo="Hola <img src=x onerror=alert(1)>", excerpt="<script>x</script>Ok")
        limpio, informe = ba.sanear_borrador(dirty, WP_URL)
        self.assertEqual(informe["campos"], ["titulo", "excerpt"])
        self.assertEqual(limpio["titulo"], "Hola")
        self.assertEqual(limpio["excerpt"], "Ok")
        self.assertIn("titulo", ba.resumen_saneado(informe))

    def test_missing_fields_become_empty_strings(self):
        limpio, informe = ba.sanear_borrador({"html": "<p>x</p>"}, WP_URL)
        for campo in ba.TOPES_CAMPOS:
            self.assertEqual(limpio[campo], "")
        self.assertEqual(informe["campos"], [])


if __name__ == "__main__":
    unittest.main()
