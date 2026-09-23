# notion-wp-blog-agent

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.9+-37734A?logo=python&logoColor=white)](https://www.python.org/) [![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)

**🌐 English** en [README.md](README.md) · **Español aquí**

Agente de blog Notion → WordPress con IA: investigación SERP, guías de estilo por cliente y borradores con revisión humana por Telegram.

Tú escribes keyword + enfoque en **Notion**. Un cron en tu VPS redacta con **IA** (redactor + editor, con los top resultados de Google como base), lo sube a **WordPress** como borrador y te avisa por **Telegram**. Revisas, pones foto y publicas.

> **Filosofía:** el agente *redacta*, tú *decides*. Nunca publica — siempre borrador. Empieza seguro (`DRY_RUN=true` simula sin tocar WordPress).

Ver [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/NOTION_SETUP.md`](docs/NOTION_SETUP.md) y [`docs/DEPLOY_VPS.md`](docs/DEPLOY_VPS.md).

## Arranque rápido

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Notion / OpenAI / Serper / Telegram
cp wp_credentials.example.json wp_credentials.json  # una entrada por web
python blog_automation.py  # necesita una fila Pendiente en Notion
```

## Cómo funciona

1. **Tú** metes keyword + enfoque en `Artículos` (segundos).
2. **La IA** investiga el top Google, sintetiza sin copiar. Objetivo ~1150 palabras, editor verifica checklist del cliente.
3. **Borrador WP**: título SEO, meta, slug, extracto, tags, categoría, enlaces internos + conversión a home. Nunca publicado.
4. **Aviso Telegram** con enlace directo + conteo de palabras.
5. **Tú** revisas, foto y publicas.

Reglas por cliente en Notion (`Clientes` → contenido de la página = guía). Cupo mensual respetado, slugs únicos, lock anti-solape de cron.

## Seguridad

Saneado: sin hosts, tokens ni claves reales, solo placeholders. Secretos en `.env` / `wp_credentials.json` (gitignored).

## Licencia

[MIT](LICENSE) © 2026 VerticeDev. Úsalo, modifícalo y compártelo; atribución apreciada. Sin garantía.
