# notion-wp-blog-agent

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.9+-37734A?logo=python&logoColor=white)](https://www.python.org/) [![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)

**🌐 English** · [Español](README.es.md)

AI-assisted Notion → WordPress blog agent: SERP research, per-client style guides and human-in-the-loop drafts via Telegram.

You write the keyword + angle in **Notion**. A cron job on your VPS writes the article with **AI** (writer + editor passes, grounded on the top Google results), uploads it to **WordPress** as a draft, and pings you on **Telegram**. You review, add the photo, publish.

> **Philosophy:** the agent *drafts*, you *decide*. It never publishes — always draft. It starts safe (`DRY_RUN=true` simulates without touching WordPress).

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design, [`docs/NOTION_SETUP.md`](docs/NOTION_SETUP.md) for the Notion bases and [`docs/DEPLOY_VPS.md`](docs/DEPLOY_VPS.md) to run it 24/7.

## Quickstart

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Notion / OpenAI / Serper / Telegram
cp wp_credentials.example.json wp_credentials.json  # one entry per site
python blog_automation.py  # needs one Pendiente row in Notion to do anything
```

## How it works

1. **You** add keyword + angle in Notion `Artículos` (seconds per article).
2. **AI drafts** with SERP research: top Google results are downloaded and synthesized, never copied. Writer pass aims ~1150 words, editor pass enforces the client's checklist.
3. **WordPress draft**: SEO title, meta description, slug, excerpt, tags, category, internal links + conversion link to home. Never published.
4. **Telegram ping** with direct edit link + word count.
5. **You** review (2 min), add the photo, publish when ready.

Per-client rules live in Notion (`Clientes` → page content = style guide). Monthly quota (`Cupo/mes`) is enforced; slugs are deduplicated; overlapping cron runs are locked out.

## Repo layout

```
blog_automation.py          # the agent (single file)
guides/style-guide.example.md  # template client guide
tests/                      # unit tests (no credentials needed)
docs/
  ARCHITECTURE.md
  NOTION_SETUP.md
  DEPLOY_VPS.md
CHANGELOG.md
```

## Placeholders & security

Sanitized: no real hosts, tokens, chat IDs or keys — only placeholders. Secrets live in `.env` / `wp_credentials.json`, both gitignored. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#security).

## License

[MIT](LICENSE) © 2026 VerticeDev. Use, modify and share freely; attribution appreciated. No warranty.
