"""
notion-wp-blog-agent — Notion → AI (SERP research) → WordPress draft.

Reads pending jobs (Estado = Pendiente) from the "Articulos" Notion database,
generates the article with AI in two passes (writer + editor) using Google
SERP research (Serper), uploads it to WordPress as a draft, notifies via
Telegram and updates the status in Notion.

Each client website has its own style guide (a Notion page). The agent
follows ONLY that client's guide — never mixes rules between clients.

Designed to run via cron on a VPS. It never publishes — always draft,
human review required. Starts safe: DRY_RUN=true only simulates.
"""

import os
import re
import sys
import json
import html
import atexit
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("blog automation")

# --- Configuración (todo por env, nada hardcodeado) ---
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_VERSION = "2022-06-28"
ARTICULOS_DB_ID = os.environ["NOTION_ARTICULOS_DB_ID"]

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
OPENAI_MAX_TOKENS = int(os.environ.get("OPENAI_MAX_TOKENS", "3500"))

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERP_NUM_RESULTADOS = int(os.environ.get("SERP_NUM_RESULTADOS", "3"))

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

WP_CREDENTIALS_FILE = os.environ.get("WP_CREDENTIALS_FILE", "wp_credentials.json")
LOCK_FILE = os.environ.get("LOCK_FILE", "/tmp/blog_automation.lock")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in ("1", "true", "yes")

# Mapa opcional dominio -> nombre de autor WP. Ej:
# AUTHOR_MAP_JSON='{"example.com":"Example Author"}'
try:
    AUTHOR_MAP = json.loads(os.environ.get("AUTHOR_MAP_JSON", "{}"))
except json.JSONDecodeError:
    AUTHOR_MAP = {}


def parse_json_robusto(texto):
    """Extrae JSON aunque venga con fences o comas finales."""
    t = texto.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?", "", t).strip()
        t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        ini = t.find("{")
        fin = t.rfind("}")
        if ini >= 0 and fin > ini:
            candidato = re.sub(r",\s*}", "}", t[ini : fin + 1])
            candidato = re.sub(r",\s*]", "]", candidato)
            return json.loads(candidato)
        raise


def get_desired_author(wp_url):
    """Nombre de autor configurado para ese dominio, o None."""
    try:
        domain = urlparse(wp_url).netloc.lower()
    except Exception:
        return None
    for key, val in AUTHOR_MAP.items():
        if key.lower().rstrip("/") in domain:
            return val
    return None


NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

openai_client = OpenAI(api_key=OPENAI_API_KEY)


def acquire_lock():
    """Evita dos ejecuciones solapadas de cron."""
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)

        def _release():
            try:
                os.unlink(LOCK_FILE)
            except OSError:
                pass

        atexit.register(_release)
        return True
    except FileExistsError:
        log.warning("Otra ejecución en curso (lock %s), salgo.", LOCK_FILE)
        return False


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def notion_get_pending_articles():
    """Artículos con Estado = Pendiente."""
    url = f"https://api.notion.com/v1/databases/{ARTICULOS_DB_ID}/query"
    body = {"filter": {"property": "Estado", "select": {"equals": "Pendiente"}}}
    r = requests.post(url, headers=NOTION_HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["results"]


def notion_get_page(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    r = requests.get(url, headers=NOTION_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def notion_get_page_text(page_id):
    """Texto plano del contenido de una página (guía de estilo del cliente)."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    texts = []
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(url, headers=NOTION_HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        for block in data["results"]:
            block_type = block["type"]
            rich_text = block.get(block_type, {}).get("rich_text", [])
            line = "".join(t.get("plain_text", "") for t in rich_text)
            if line:
                texts.append(line)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return "\n".join(texts)


def notion_update_article(page_id, estado, enlace=None, nota=None):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {"Estado": {"select": {"name": estado}}}
    if enlace:
        properties["Enlace al borrador"] = {"url": enlace}
    if nota is not None:
        properties["Nota"] = {"rich_text": [{"text": {"content": nota[:2000]}}]}
    r = requests.patch(url, headers=NOTION_HEADERS, json={"properties": properties}, timeout=30)
    r.raise_for_status()


def notion_article_fields(article):
    props = article["properties"]

    def plain(prop):
        return "".join(t.get("plain_text", "") for t in props[prop].get("rich_text", []))

    def title(prop):
        return "".join(t.get("plain_text", "") for t in props[prop].get("title", []))

    cliente_rel = props["Cliente"]["relation"]
    cliente_id = cliente_rel[0]["id"] if cliente_rel else None
    return {
        "id": article["id"],
        "articulo": title("Artículo"),
        "keyword": plain("Keyword"),
        "enfoque": plain("Enfoque"),
        "cliente_id": cliente_id,
    }


def notion_client_fields(page_id):
    page = notion_get_page(page_id)
    props = page["properties"]
    titulo = "".join(t.get("plain_text", "") for t in props["Cliente"]["title"])
    cupo = props["Cupo/mes"]["number"]
    guia = notion_get_page_text(page_id)
    return {"wp_url": titulo.rstrip("/"), "cupo": cupo, "guia_estilo": guia}


def notion_count_usados_mes(cliente_page_id):
    """Artículos de ese cliente creados este mes con Estado != Pendiente."""
    primero_mes = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    primero_str = primero_mes.strftime("%Y-%m-%d")
    url = f"https://api.notion.com/v1/databases/{ARTICULOS_DB_ID}/query"
    usados = 0
    cursor = None
    while True:
        body = {
            "filter": {
                "and": [
                    {"property": "Cliente", "relation": {"contains": cliente_page_id}},
                    {"timestamp": "created_time", "created_time": {"on_or_after": primero_str}},
                ]
            },
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(url, headers=NOTION_HEADERS, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        for item in data.get("results", []):
            try:
                estado = item["properties"]["Estado"]["select"]["name"]
            except Exception:
                estado = ""
            if estado and estado != "Pendiente":
                usados += 1
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return usados


# ---------------------------------------------------------------------------
# WordPress
# ---------------------------------------------------------------------------

def load_wp_credentials():
    with open(WP_CREDENTIALS_FILE) as f:
        return json.load(f)


def wp_auth_for(wp_url, creds):
    for key, val in creds.items():
        if key.rstrip("/") == wp_url:
            return (val["wp_user"], val["wp_app_password"])
    return None


def wp_fetch_reference_posts(wp_url, n=3):
    url = f"{wp_url}/wp-json/wp/v2/posts"
    params = {"per_page": n, "_fields": "title,content"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    posts = []
    for p in r.json():
        title = p["title"]["rendered"]
        content_text = re.sub("<[^<]+?>", "", p["content"]["rendered"])
        posts.append({"title": title, "text": content_text.strip()[:3000]})
    return posts


def wp_fetch_categories(wp_url, auth):
    url = f"{wp_url}/wp-json/wp/v2/categories"
    r = requests.get(url, params={"per_page": 100}, auth=auth, timeout=30)
    r.raise_for_status()
    return {c["name"].lower(): c["id"] for c in r.json()}


def wp_slug_exists(wp_url, slug, auth):
    try:
        r = requests.get(
            f"{wp_url}/wp-json/wp/v2/posts",
            params={"slug": slug, "_fields": "id"},
            auth=auth,
            timeout=30,
        )
        r.raise_for_status()
        return len(r.json()) > 0
    except Exception as e:
        log.warning("No pude comprobar slug %s: %s", slug, e)
        return False


def wp_unique_slug(wp_url, slug_base, auth):
    slug = slug_base
    for i in range(2, 7):
        if not wp_slug_exists(wp_url, slug, auth):
            return slug
        slug = f"{slug_base}-{i}"
    return slug


def wp_fetch_related(wp_url, keyword, n=2):
    """Posts existentes para enlazado interno (búsqueda pública)."""
    try:
        q = " ".join(keyword.split()[:4])
        r = requests.get(
            f"{wp_url}/wp-json/wp/v2/posts",
            params={"search": q, "per_page": n, "_fields": "link,title"},
            timeout=30,
        )
        r.raise_for_status()
        out = []
        for p in r.json():
            titulo = re.sub("<[^>]+>", "", p.get("title", {}).get("rendered", ""))
            out.append({"titulo": titulo, "url": p.get("link", "")})
        return [x for x in out if x["url"]][:n]
    except Exception as e:
        log.warning("Sin relacionados (%s)", e)
        return []


def wp_ensure_tags(wp_url, auth, tags):
    ids = []
    for name in (tags or [])[:5]:
        name = str(name).strip()[:40]
        if not name:
            continue
        try:
            r = requests.get(
                f"{wp_url}/wp-json/wp/v2/tags",
                params={"search": name, "per_page": 5},
                auth=auth,
                timeout=30,
            )
            r.raise_for_status()
            found = None
            for t in r.json():
                if t["name"].lower() == name.lower():
                    found = t
                    break
            if found:
                ids.append(found["id"])
            else:
                c = requests.post(
                    f"{wp_url}/wp-json/wp/v2/tags", auth=auth, json={"name": name}, timeout=30
                )
                if c.status_code in (200, 201):
                    ids.append(c.json()["id"])
        except Exception as e:
            log.warning("Tag %s no creado: %s", name, e)
    return ids


def wp_ensure_author(wp_url, auth, desired_name):
    """ID de usuario por nombre. None si no existe."""
    if not desired_name:
        return None
    try:
        r = requests.get(
            f"{wp_url}/wp-json/wp/v2/users",
            params={"search": desired_name, "per_page": 10},
            auth=auth,
            timeout=30,
        )
        r.raise_for_status()
        for u in r.json():
            if u.get("name", "").lower() == desired_name.lower():
                return u["id"]
        users = r.json()
        if users:
            return users[0]["id"]
    except Exception as e:
        log.warning("No pude resolver autor %s: %s", desired_name, e)
    return None


def wp_publish_draft(wp_url, auth, draft, category_id=None, tag_ids=None, author_id=None):
    """Publica borrador. Devuelve (edit_link, meta_ok). Reintenta sin autor/meta."""
    if DRY_RUN:
        log.info("[DRY_RUN] no publico, simulo: %s", draft.get("titulo"))
        return f"{wp_url}/wp-admin/edit.php?post_status=draft&post_type=post", True
    url = f"{wp_url}/wp-json/wp/v2/posts"
    body = {
        "title": draft["titulo"],
        "content": draft["html"],
        "status": "draft",
        "slug": draft["slug"],
        "excerpt": draft.get("excerpt", ""),
        "meta": {
            "_yoast_wpseo_title": draft["meta_titulo"],
            "_yoast_wpseo_metadesc": draft["meta_descripcion"],
        },
    }
    if category_id:
        body["categories"] = [category_id]
    if tag_ids:
        body["tags"] = tag_ids
    if author_id:
        body["author"] = author_id
    r = requests.post(url, auth=auth, json=body, timeout=60)
    if r.status_code in (401, 403):
        log.warning("WP %s, reintento sin autor. Resp: %s", r.status_code, r.text[:500])
        body.pop("author", None)
        r = requests.post(url, auth=auth, json=body, timeout=60)
    if r.status_code in (400, 403) and "meta" in r.text.lower():
        log.warning("WP rechazó meta Yoast, reintento sin meta. Añadir filtro en functions.php.")
        body.pop("meta", None)
        r = requests.post(url, auth=auth, json=body, timeout=60)
    try:
        r.raise_for_status()
    except Exception:
        log.error("WP publish falló %s: %s", r.status_code, r.text[:1000])
        raise
    post = r.json()
    meta_ok = "meta" in body
    return f"{wp_url}/wp-admin/post.php?post={post['id']}&action=edit", meta_ok


# ---------------------------------------------------------------------------
# Investigación SERP (Google vía Serper + descarga y limpieza)
# ---------------------------------------------------------------------------

def serper_buscar_top(keyword, enfoque, n=None):
    """Top N resultados orgánicos. Devuelve [{titulo, url, snippet}]."""
    if not SERPER_API_KEY:
        log.warning("SERPER_API_KEY vacío: salto investigación SERP.")
        return []
    n = n or SERP_NUM_RESULTADOS
    q = f"{keyword} {enfoque}".strip() if enfoque else keyword
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": q, "gl": "es", "hl": "es", "num": n},
            timeout=30,
        )
        r.raise_for_status()
        organicos = r.json().get("organic", [])[:n]
        out = []
        for item in organicos:
            url = item.get("link", "")
            if not url:
                continue
            out.append({"titulo": item.get("title", ""), "url": url, "snippet": item.get("snippet", "")})
        return out
    except Exception as e:
        log.warning("Fallo Serper (%s), sigo sin SERP.", e)
        return []


def descargar_texto_url(url, max_chars=4000):
    """Descarga una URL y devuelve texto plano limpio."""
    try:
        r = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; blog-agent/1.0)"}, timeout=20
        )
        r.raise_for_status()
        soup_html = r.text
        soup_html = re.sub(
            r"(?is)<(script|style|nav|footer|header|noscript|form).*?>.*?</\1>", " ", soup_html
        )
        text = re.sub(r"(?s)<[^>]+>", " ", soup_html)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        log.warning("No pude descargar %s (%s)", url, e)
        return ""


def investigar_serp(keyword, enfoque, n=None):
    """Busca top Google y descarga contenido."""
    top = serper_buscar_top(keyword, enfoque, n=n)
    investigacion = []
    for item in top:
        texto = descargar_texto_url(item["url"])
        investigacion.append({**item, "texto": texto})
    return investigacion


# ---------------------------------------------------------------------------
# IA (dos pasadas: redactor + editor, guías por cliente)
# ---------------------------------------------------------------------------

def generar_borrador(keyword, enfoque, guia_estilo, referencias, investigacion=None, home_url=""):
    ref_text = "\n\n".join(
        f"### {r['title']}\n{r['text'][:1500]}" for r in referencias
    ) or "(sin artículos de referencia disponibles todavía)"

    investigacion = investigacion or []
    if investigacion:
        partes = []
        for i, r in enumerate(investigacion, 1):
            texto = (r.get("texto") or "")[:2500]
            partes.append(
                f"--- Fuente SERP {i} ---\nTítulo: {r.get('titulo','')}\n"
                f"URL: {r.get('url','')}\nSnippet: {r.get('snippet','')}\nContenido: {texto}"
            )
        serp_text = "\n\n".join(partes)
    else:
        serp_text = "(sin investigación SERP)"

    system = (
        "Eres redactor SEO senior en español. Cada web tiene su propia guía de estilo: "
        "la sigues al 100%, sin mezclar reglas de otros clientes. Sintetizas la SERP, no copias. "
        "Nunca suenas a IA genérica. Devuelve solo JSON válido."
    )
    user = f"""Guía de estilo de ESTA web (manda sobre todo lo demás salvo longitud):
{guia_estilo}

Artículos de referencia de la propia web (para el TONO, NO para copiar):
{ref_text}

Investigación top Google (para el FONDO, sintetiza, no copies):
{serp_text}

Escribe un artículo de blog nuevo.
Palabra clave objetivo: {keyword}
Enfoque: {enfoque}
HOME_URL del cliente: {home_url}

Enlaces obligatorios en el html:
- 1-2 internos inline con anchor natural dentro de frases (no URL pegada).
- 1 siempre a HOME_URL a modo conversión, aunque ya haya bloque Leer también.

Requisitos base de LONGITUD (manda esto, ignora otros rangos de la guía):
- OBJETIVO 1150 palabras, RANGO 1000-1250.
- Keyword natural, sin forzarla.

Devuelve un JSON con estas claves exactas:
- "titulo": H1 según guía, sin mayúsculas ni keyword forzada
- "meta_titulo": natural máximo 60 caracteres
- "meta_descripcion": natural 140-156 caracteres
- "slug": minúsculas con guiones
- "categoria_sugerida": 1-2 palabras
- "excerpt": natural 1-2 frases max 160
- "tags": 3-5 etiquetas cortas
- "html": cuerpo HTML SOLO con (p, h2, h3, ul, ol, li, strong). PROHIBIDO <h1>. Empieza con <p>."""

    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_completion_tokens=OPENAI_MAX_TOKENS,
    )
    try:
        return parse_json_robusto(resp.choices[0].message.content)
    except json.JSONDecodeError as e:
        log.warning("JSON truncado (%s), reintento una vez.", e)
        resp2 = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        return parse_json_robusto(resp2.choices[0].message.content)


def revisar_borrador(draft, guia_estilo, keyword):
    html_actual = draft.get("html", "")
    num_palabras = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", html_actual)))
    system = (
        "Eres editor exigente. Verificas la guía de ESE cliente, no la de otros. "
        "Devuelve solo JSON válido."
    )
    user = f"""Guía de estilo:
{guia_estilo}

Palabra clave: {keyword}
Palabras actuales (aprox): {num_palabras} (objetivo 1150, rango 1000-1250)

Borrador a revisar (HTML):
{html_actual}

Checklist (si falla, NO está ok y lo corriges tú):
1. Longitud y H2/FAQ/vocab/enlaces/CTA según SU guía. Si <1000 amplías, si >1250 recortas a 1150.
2. Nada prohibido por SU guía (mayúsculas, FAQ rutina, URL pegada, fórmulas plantilla).
3. Sin <h1> en el html. Con enlace inline + conversión a home.

Devuelve JSON exacto:
- "ok": true solo si 1000-1400 Y checklist ok, si no false
- "html_corregido": HTML completo corregido
- "nota": qué cambiaste o por qué ojo humano"""

    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return parse_json_robusto(resp.choices[0].message.content)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def avisar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": texto}, timeout=15)


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------

def procesar_articulo(article_raw, wp_creds):
    datos = notion_article_fields(article_raw)

    if not datos["cliente_id"]:
        notion_update_article(datos["id"], "Revisar")
        avisar_telegram(f"Artículo sin cliente enlazado: {datos['articulo'] or datos['keyword']}")
        return

    if not datos["keyword"]:
        notion_update_article(datos["id"], "Revisar", nota="Falta Keyword en Notion")
        return

    cliente = notion_client_fields(datos["cliente_id"])
    auth = wp_auth_for(cliente["wp_url"], wp_creds)
    if not auth:
        notion_update_article(datos["id"], "Revisar")
        avisar_telegram(f"Faltan credenciales WordPress para {cliente['wp_url']}")
        return

    try:
        if cliente.get("cupo"):
            usados = notion_count_usados_mes(datos["cliente_id"])
            log.info("Cupo %s: %s/%s", cliente["wp_url"], usados, cliente["cupo"])
            if usados >= cliente["cupo"]:
                msg = f"Cupo mensual alcanzado ({usados}/{cliente['cupo']})"
                notion_update_article(datos["id"], "Revisar", nota=msg)
                avisar_telegram(f"{cliente['wp_url']}\n{msg}: {datos['keyword']}")
                return
    except Exception as e:
        log.warning("No pude comprobar cupo, sigo igual: %s", e)

    referencias = wp_fetch_reference_posts(cliente["wp_url"])
    log.info("Investigando SERP para: %s...", datos["keyword"])
    investigacion = investigar_serp(datos["keyword"], datos["enfoque"])
    log.info("SERP: %s fuentes.", len(investigacion))
    draft = generar_borrador(
        datos["keyword"], datos["enfoque"], cliente["guia_estilo"],
        referencias, investigacion, home_url=cliente["wp_url"],
    )
    revision = revisar_borrador(draft, cliente["guia_estilo"], datos["keyword"])
    draft["html"] = revision.get("html_corregido") or draft["html"]

    draft["html"] = re.sub(r"(?is)<h1.*?>.*?</h1>", "", draft["html"]).strip()
    home = cliente["wp_url"].rstrip("/") + "/"
    if home not in draft["html"]:
        draft["html"] += (
            f'<p>Si te reconoces en esto, <a href="{home}">pide ayuda con un plan serio en nuestro centro</a>.</p>'
        )

    try:
        relacionados = wp_fetch_related(cliente["wp_url"], datos["keyword"])
        relacionados = [r for r in relacionados if draft.get("slug", "") not in r["url"]][:2]
        if relacionados:
            items = "".join(
                f'<li><a href="{r["url"]}">{html.escape(r["titulo"])}</a></li>' for r in relacionados
            )
            draft["html"] += f"<h2>Leer también</h2><ul>{items}</ul>"
    except Exception as e:
        log.warning("Fallo enlaces internos: %s", e)

    try:
        draft["slug"] = wp_unique_slug(cliente["wp_url"], draft.get("slug", "articulo"), auth)
    except Exception as e:
        log.warning("Fallo slug único: %s", e)

    num_palabras = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", draft["html"])))
    log.info("Artículo final: ~%s palabras.", num_palabras)

    categorias = wp_fetch_categories(cliente["wp_url"], auth)
    cat_id = categorias.get(str(draft.get("categoria_sugerida", "")).lower())
    tag_ids = wp_ensure_tags(cliente["wp_url"], auth, draft.get("tags"))
    author_id = wp_ensure_author(cliente["wp_url"], auth, get_desired_author(cliente["wp_url"]))

    link, meta_ok = wp_publish_draft(cliente["wp_url"], auth, draft, cat_id, tag_ids, author_id)

    estado = "Generado" if revision.get("ok") and 1000 <= num_palabras <= 1400 else "Revisar"
    home_ok = home in draft["html"]
    h1_ok = "<h1" not in draft["html"].lower()
    nota = (
        f"[{num_palabras} palabras | {len(investigacion)} fuentes SERP | "
        f"H1 fuera:{'sí' if h1_ok else 'no'} | conv_home:{'sí' if home_ok else 'no'}]"
        f"{'' if meta_ok else ' Meta Yoast no guardado'}"
    ).strip()
    notion_update_article(datos["id"], estado, link, nota or None)

    aviso = f"{cliente['wp_url']}\n{draft['titulo']}\n~{num_palabras} palabras\n{link}"
    if estado == "Revisar":
        aviso += f"\n\nRevisar: {nota}"
    avisar_telegram(aviso)


def main():
    if not acquire_lock():
        return
    wp_creds = load_wp_credentials()
    pendientes = notion_get_pending_articles()
    if not pendientes:
        log.info("Sin artículos pendientes.")
        return
    for article_raw in pendientes:
        page_id = article_raw["id"]
        try:
            procesar_articulo(article_raw, wp_creds)
        except Exception as e:
            try:
                notion_update_article(page_id, "Revisar", nota=f"Error: {e}"[:2000])
            except Exception:
                pass
            try:
                avisar_telegram(f"Error generando artículo: {e}")
            except Exception:
                pass
            log.exception("Error en %s: %s", page_id, e)


if __name__ == "__main__":
    main()
