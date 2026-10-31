# notion-wp-blog-agent

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.9+-37734A?logo=python&logoColor=white)](https://www.python.org/) [![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)

**🌐 English** · [Español](README.es.md)

AI-assisted Notion → WordPress blog agent: Google SERP research, per-client style guides and human-in-the-loop drafts via Telegram.

You write the keyword + angle in **Notion** (seconds per article). A cron job on your VPS researches the top Google results, writes the article with **AI** in two passes (writer + editor), uploads it to **WordPress as a draft** (SEO title, meta, slug, excerpt, tags, category, internal + conversion links), and pings you on **Telegram** with a direct edit link. You review for 2 minutes, add the photo, publish when ready.

> **Philosophy:** the agent *drafts*, you *decide*. It never publishes. It starts safe (`DRY_RUN=true` simulates end-to-end without touching WordPress).

## Why this exists

Single-pass AI posts are short, generic and literal: ~370 words, keyword stuffed, FAQ with 2-line answers, zero research. This agent fixes that:

- **SERP-grounded**: top N Google results (Serper) are downloaded, cleaned and synthesized — never copied.
- **Per-client voice**: each website owns a full style guide (Notion page). The model follows ONLY that client's guide: tone, banned formulas, structure, internal-linking and CTA rules.
- **Real length**: writer targets ~1150 words; editor enforces the checklist and the 1000-1400 window.
- **WordPress-complete**: excerpt, tags (existing ones only — new suggestions go to the Notion note), category match, unique slug, related-posts box, conversion link to home, author mapping, Yoast meta with graceful fallback.
- **Ops-safe**: monthly quota per client (fails closed), `flock` cron lock, `En curso` state so a crashed run never regenerates duplicate drafts, factual short notes (LLM prose notes hallucinate), dry-run mode.
- **Hardened for untrusted input**: the model reads third-party pages, so its output is treated as hostile. Allowlist HTML sanitizer right before posting (`p, h2, h3, ul, ol, li, strong, em, a` — links only to the client's own `https` domain), SSRF-guarded downloads (https, public IPs only, redirects re-validated, 1.5 MB / 20 s caps), secrets redacted from logs, Notion and Telegram.

Typical result: 370 → 1100-1500 words, review time 2 min + photo.

## Quickstart

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Notion / OpenAI / Serper / Telegram
cp wp_credentials.example.json wp_credentials.json  # one entry per site
python blog_automation.py  # needs one Pendiente row in Notion
```

Full setup: [`docs/NOTION_SETUP.md`](docs/NOTION_SETUP.md) · [`docs/DEPLOY_VPS.md`](docs/DEPLOY_VPS.md) · design [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · prompts [`docs/PROMPTS.md`](docs/PROMPTS.md) · costs [`docs/COSTS.md`](docs/COSTS.md) · fixes [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## How it works (5 steps)

1. **You brief** — new row in Notion `Artículos`: client + `Keyword` + `Enfoque`, state `Pendiente`.
2. **Agent researches** — Serper top 3 for `keyword + enfoque`, downloads each page (https to public IPs only, size and time capped), strips scripts/nav/footer → clean text, passed to the model clearly marked as untrusted data.
3. **Agent writes** — row → `En curso`, then writer JSON (`titulo, meta_titulo, meta_descripcion, slug, categoria_sugerida, excerpt, tags, html`), then editor pass against the client's guide (length, H2 rules, vocab bans, links, CTA, no `<h1>` in body).
4. **Agent drafts** — cleanup (guarantee home link, append related box, unique slug) → allowlist sanitizer (drops `<h1>`, scripts, iframes, attributes, external links; title/excerpt/meta become plain text) → `POST /wp-json/wp/v2/posts` with `status=draft`.
5. **You review** — Notion row → `Generado` (good) or `Revisar` (read Nota: length, quota, anything the sanitizer removed, suggested new tags) + Telegram ping with word count and edit link.

## Multi-client onboarding (new site in ~10 min)

1. Client sends: site URL, monthly quota, author display name, full style guide markdown (see [`guides/style-guide.example.md`](guides/style-guide.example.md)).
2. You: new row in Notion `Clientes` (title = `https://` URL, `Cupo/mes`, paste guide inside the page) + dedicated WP user (Author or Contributor role) + app password in `wp_credentials.json` + optional `AUTHOR_MAP_JSON` entry.
3. Test: one `Pendiente` row → `python blog_automation.py` → check draft → feedback → done. No code changes.

## Repo layout

```
blog_automation.py              # the agent (single file)
guides/style-guide.example.md   # template client guide
tests/                          # offline tests (network mocked): python -m pytest tests/ -q
docs/
  ARCHITECTURE.md               # design + decisions + security
  NOTION_SETUP.md               # databases, properties, states
  DEPLOY_VPS.md                 # VPS, WordPress, cron
  PROMPTS.md                    # writer/editor prompts explained
  COSTS.md                      # per-article math + volume table
  TROUBLESHOOTING.md            # every error we hit in production
CHANGELOG.md / CONTRIBUTING.md / LICENSE (MIT)
```

## Placeholders & security

Sanitized by design: no real hosts, tokens, chat IDs, keys or client content — only `example.com` placeholders. Secrets live in `.env` / `wp_credentials.json` (both gitignored). Least privilege everywhere: per-site WP app passwords, Notion integration scoped to the two DBs, Telegram token in env. Details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#security).

Recommended hardening for every site (step by step in [`docs/DEPLOY_VPS.md`](docs/DEPLOY_VPS.md)):

- **Dedicated WordPress user with the Author or Contributor role** — neither has `unfiltered_html`, so WordPress filters whatever the agent posts as a second layer behind its own sanitizer. Never an Administrator.
- **`define('DISALLOW_UNFILTERED_HTML', true);`** in `wp-config.php`, so no role (not even an admin whose app password leaks) can store raw scripts.
- **`https://` site URLs only** — the Notion `Cliente` title and the `wp_credentials.json` keys. The agent refuses plain `http` (credentials would travel in clear).
- **Log file mode `0640` with logrotate**, owned by the unprivileged cron user.

## License

[MIT](LICENSE) © 2026 VerticeDev. Use, modify and share freely; attribution appreciated. No warranty.
