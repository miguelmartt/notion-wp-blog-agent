# TROUBLESHOOTING — every production failure, in order

## `SERP: 0 fuentes`
Serper returned nothing. Check in order: `grep ^SERPER_API_KEY .env` present?
`key_len` ~32? Serper Dashboard → Logs (401 = bad key, 429 = quota)? Single-test the query in Serper Playground.
Code degrades gracefully: drafts without SERP (thin — fix the key, don't bulk-run).

## `403 Forbidden` on `POST /wp-json/wp/v2/posts`
Almost always **author assignment**: an `Author`-role user cannot publish as another author.
Fix: automation user → **Editor** (`Users → Automation → Editor`). Code retries without `author` so the run still drafts (as the automation user) instead of dying.
Verify: `GET /wp/v2/users/me` with the app password must return 200; 401/403 = revoked password or role.

## `posts.json` attachment in Telegram
Not a bug: your error text contains the `wp-json` URL and Telegram previews it as a file. Ignore it, read the `403/400` line above.

## `max_tokens is not supported, use max_completion_tokens`
`gpt-5.x` renamed the param. Code uses `max_completion_tokens` (`OPENAI_MAX_TOKENS`, default 3500).

## `JSONDecodeError: Unterminated string`
`max_completion_tokens` too low truncated the JSON mid-HTML. Raise it (3500 works for ~1500 words) — the code retries once and strips fences/trailing commas via `parse_json_robusto`.

## `Word count keeps overshooting (1500 → 1700+)`
LLMs estimate, don't count (±15% normal). Fix: aim **below** the cap (1150 for a 1250 cap) + editor trims to range. Chasing exact counts is futile — accept a ±150 band.

## `Meta Yoast not saved`
WP 400s `meta` unless exposed via REST. Add the `register_meta(..., show_in_rest)` filter in `functions.php` (see DEPLOY_VPS.md). Code retries without meta and flags it in Nota.

## `ModuleNotFoundError: dotenv`
You ran system python, not the venv: `source venv/bin/activate` first.

## `Otra ejecución en curso (lock)`
Cron overlapped a long run. The second run exits by design (`LOCK_FILE`). Lengthen the cron interval instead of disabling the lock.

## `Cupo mensual alcanzado`
Not an error: client hit `Cupo/mes`. Row → `Revisar` with `(usados/cupo)`. Raise quota or wait for next month.

## Download `403` (Mayo Clinic et al.)
Some sites block bots. Warning only — the run continues with the remaining sources.

## Notion `Nota` sounds invented
It was: v1 stored the editor's free prose. Now Nota is factual code-built: `[words | sources | H1 fuera | conv_home]`.
