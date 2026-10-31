# notion-wp-blog-agent

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.9+-37734A?logo=python&logoColor=white)](https://www.python.org/) [![CI](https://github.com/miguelmartt/notion-wp-blog-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/miguelmartt/notion-wp-blog-agent/actions/workflows/ci.yml)

**🌐 English** en [README.md](README.md) · **Español aquí**

Agente de blog Notion → WordPress con IA: investigación en Google, guías de estilo por cliente y borradores con revisión humana por Telegram.

Escribes keyword + enfoque en **Notion** (segundos por artículo). Un cron en tu VPS investiga el top de Google, redacta con **IA** en dos pasadas (redactor + editor), lo sube a **WordPress como borrador** (título SEO, meta, slug, extracto, tags, categoría, enlaces internos + conversión) y te avisa por **Telegram** con enlace directo. Revisas 2 minutos, pones foto y publicas.

> **Filosofía:** el agente *redacta*, tú *decides*. Nunca publica. Empieza seguro (`DRY_RUN=true` simula sin tocar WordPress).

## Por qué existe

La IA de una pasada sale corta, genérica y literal: ~370 palabras, keyword forzada, FAQ de 2 líneas, cero investigación. Este agente lo corrige:

- **Con investigación**: top N de Google (Serper) descargado, limpiado y sintetizado — jamás copiado.
- **Voz por cliente**: cada web tiene su guía completa (página de Notion). El modelo sigue SOLO la de ese cliente: tono, fórmulas prohibidas, estructura, enlaces y CTA.
- **Longitud real**: redactor objetivo ~1150 palabras; editor impone checklist y ventana 1000-1400.
- **WP completo**: extracto, tags (solo las que ya existen; las nuevas van como sugerencia a la Nota de Notion), categoría, slug único, bloque relacionados, enlace conversión a home, autor, meta Yoast con fallback.
- **Seguro en producción**: cupo mensual por cliente (si no se puede comprobar, no genera), lock de cron con `flock`, estado `En curso` para que un fallo a mitad no regenere borradores duplicados, notas factuales cortas (las literarias alucinan), modo dry-run.
- **Blindado frente a contenido no fiable**: el modelo lee webs de terceros, así que su salida se trata como hostil. Saneado por lista blanca justo antes de publicar (`p, h2, h3, ul, ol, li, strong, em, a`, con enlaces solo al dominio `https` del propio cliente), descargas protegidas contra SSRF (solo https a IPs públicas, redirecciones revalidadas, topes de 1,5 MB y 20 s) y secretos redactados en logs, Notion y Telegram.

Resultado típico: 370 → 1100-1500 palabras, revisión 2 min + foto.

## Arranque rápido

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Notion / OpenAI / Serper / Telegram
cp wp_credentials.example.json wp_credentials.json  # una entrada por web
python blog_automation.py  # necesita una fila Pendiente en Notion
```

Docs: [`docs/NOTION_SETUP.md`](docs/NOTION_SETUP.md) · [`docs/DEPLOY_VPS.md`](docs/DEPLOY_VPS.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/PROMPTS.md`](docs/PROMPTS.md) · [`docs/COSTS.md`](docs/COSTS.md) · [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Cómo funciona (5 pasos)

1. **Tú pides** — fila en `Artículos`: cliente + `Keyword` + `Enfoque`, estado `Pendiente`.
2. **Investiga** — Serper top 3 de `keyword + enfoque`, descarga cada página (solo https a IPs públicas, con topes de tamaño y tiempo), la limpia y se la pasa al modelo marcada como dato no fiable.
3. **Redacta** — fila a `En curso` y JSON (`titulo, meta_titulo, meta_descripcion, slug, categoria_sugerida, excerpt, tags, html`) y segunda pasada editora contra la guía del cliente (longitud, H2, vocabulario, enlaces, CTA, sin `<h1>` en cuerpo).
4. **Borrador WP** — limpieza (home garantizado, relacionados, slug único) → saneado por lista blanca (fuera `<h1>`, scripts, iframes, atributos y enlaces externos; título, extracto y meta a texto plano) → `POST /wp-json/wp/v2/posts` con `status=draft`.
5. **Revisas** — Notion pasa a `Generado` (bien) o `Revisar` (lee Nota: longitud, cupo, lo que haya quitado el saneado, tags nuevas sugeridas) + aviso Telegram con palabras y enlace.

## Alta de cliente nuevo (~10 min)

1. Cliente envía: URL, cupo/mes, nombre de autor, guía estilo markdown (ver [`guides/style-guide.example.md`](guides/style-guide.example.md)).
2. Tú: fila en `Clientes` (título = URL `https://`, `Cupo/mes`, pegas guía dentro) + usuario WP dedicado con rol Autor o Colaborador + app password en `wp_credentials.json` + entrada `AUTHOR_MAP_JSON` opcional.
3. Prueba: una fila `Pendiente` → `python blog_automation.py` → revisar borrador → feedback. Sin tocar código.

## Estructura

```
blog_automation.py              # el agente (un solo fichero)
guides/style-guide.example.md   # plantilla de guía
tests/                          # tests offline (red simulada): python -m pytest tests/ -q
docs/                           # ARCHITECTURE, NOTION_SETUP, DEPLOY_VPS, PROMPTS, COSTS, TROUBLESHOOTING
```

## Seguridad

Saneado: sin hosts, tokens ni contenido de clientes, solo `example.com`. Secretos en `.env` / `wp_credentials.json` (gitignored). Mínimo privilegio: app passwords por web, integración Notion solo a las dos bases, token Telegram en env.

Endurecimiento recomendado en cada web (paso a paso en [`docs/DEPLOY_VPS.es.md`](docs/DEPLOY_VPS.es.md)):

- **Usuario de WordPress dedicado con rol Autor o Colaborador**: ninguno tiene `unfiltered_html`, así que WordPress filtra lo que publica el agente como segunda capa detrás de su propio saneado. Nunca un Administrador.
- **`define('DISALLOW_UNFILTERED_HTML', true);`** en `wp-config.php`, para que ningún rol (ni un admin cuya app password se filtre) pueda guardar scripts.
- **URLs solo `https://`**: el título `Cliente` de Notion y las claves de `wp_credentials.json`. El agente rechaza `http` (las credenciales irían en claro).
- **Log con permisos `0640` y logrotate**, propiedad del usuario sin privilegios que ejecuta el cron.

## Licencia

[MIT](LICENSE) © 2026 VerticeDev. Úsalo, modifícalo y compártelo; atribución apreciada. Sin garantía.
