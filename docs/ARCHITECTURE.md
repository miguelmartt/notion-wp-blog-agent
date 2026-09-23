# ARCHITECTURE

Single-file agent (`blog_automation.py`), stdlib + `requests` + `openai` + `python-dotenv`. No framework, no DB — state lives in Notion.

## Flow

```
Notion Artículos (Pendiente)
  → Notion Clientes (guide + quota)
  → Serper top N → download + clean text
  → OpenAI writer (JSON: title/meta/slug/excerpt/tags/html)
  → OpenAI editor (enforces client checklist)
  → cleanup (strip <h1>, ensure home link, related box, unique slug)
  → WordPress REST as draft (+tags/categories/author)
  → Notion update (Generado/Revisar + factual note) + Telegram ping
```

## Key decisions

- **Per-client guides, never mixed.** Prompts say "follow THIS client's guide 100%". Each `Clientes` page holds its own full guide.
- **SERP-grounded, not copied.** Snippets + cleaned page text fed as context, model must synthesize.
- **Human-in-the-loop.** `status=draft` always. `Generado` (1000-1400 + checklist ok) vs `Revisar`.
- **Quota.** `Cupo/mes` per client counted from Notion `created_time` this month.
- **Idempotency.** Unique slug (`-2`, `-3`…), `/tmp` lock file, factual short Notion notes (LLM notes hallucinated).
- **Robust publishing.** Retries without `author` (401/403) and without `meta` (needs `functions.php` filter). See DEPLOY_VPS.md.
- **DRY_RUN.** Default true: simulates without posting to WordPress.

## Costs (2026 pricing)

Per article ≈ 8000 input + 5000 output tokens:
- `gpt-4o` ($2.5/$10 per 1M): ~$0.07
- `gpt-5.4` ($2.5/$15): ~$0.095 → 30 arts ≈ $2.85/mo
- `gpt-5.4 Pro` ($30/$180): ~$1.14 → avoid for volume

Serper: 1 search/article, negligible. Same cost whatever the site.

## Security

- No secrets in repo. `.env` + `wp_credentials.json` gitignored, only `.example` files committed.
- Least privilege: WP app password per site (Editor role to assign authors), Notion internal integration (read/write only the two DBs), Telegram bot token in env.
- JSON responses parsed defensively (`parse_json_robusto` + one retry); word counts via regex, not trust.
