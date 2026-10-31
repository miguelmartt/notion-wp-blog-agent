# TROUBLESHOOTING — every production failure, in order

## `SERP: 0 fuentes`
Serper returned nothing. Check in order: `grep ^SERPER_API_KEY .env` present?
`key_len` ~32? Serper Dashboard → Logs (401 = bad key, 429 = quota)? Single-test the query in Serper Playground.
Code degrades gracefully: drafts without SERP (thin — fix the key, don't bulk-run).

## `403 Forbidden` on `POST /wp-json/wp/v2/posts`
Almost always **author assignment**: the recommended Author/Contributor user cannot post as another author.
Expected with `AUTHOR_MAP_JSON`: the code retries without `author`, so the draft is saved as the automation user — change the author when you publish. Don't promote the user to Editor/Administrator just for this (they get `unfiltered_html` unless `DISALLOW_UNFILTERED_HTML` is set).
Verify: `GET /wp/v2/users/me` with the app password must return 200; 401/403 = revoked password or role.

## Telegram / Notion only say `Error: ConnectionError`
By design: exception text can contain URLs with tokens (`/bot<TOKEN>/`), so Notion and Telegram only get the exception type. The full traceback, with secrets redacted, is in the server log.

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
Cron overlapped a long run. The second run exits by design (`flock` on `.blog_automation.lock` next to the script). Lengthen the cron interval instead of disabling the lock. A crashed run can't leave it stuck: the kernel releases it. `PermissionError` here = the app directory isn't writable by the cron user.

## Row stuck in `En curso`
The run died hard (killed, out of memory) after marking the row. Check the log, delete any half-made draft in WordPress, and set the row back to `Pendiente`.

## `Revisar` with `Saneado, revisa el HTML: …` in Nota
The sanitizer removed something before posting: tags outside the allowlist (`script`, `iframe`, `img`, `div`…), attributes, or links that weren't `https` to the client's own domain (kept as plain text). Usually the model copied markup from a SERP page — check the draft before publishing. `URL de cliente no válida (solo https)` means the Notion `Cliente` title isn't `https://`.

## `Tags sugeridas que no existen en WP`
Not an error: the agent only assigns existing tags. Create the suggested ones in WordPress if they fit and add them to the draft.

## `No pude comprobar cupo … no genero`
Notion failed while counting the month's usage, so nothing was generated (no Serper/OpenAI spend). The row goes to `Revisar`; set it back to `Pendiente` to retry.

## `Cupo mensual alcanzado`
Not an error: client hit `Cupo/mes`. Row → `Revisar` with `(usados/cupo)`. Raise quota or wait for next month.

## Download `403` (Mayo Clinic et al.)
Some sites block bots. Warning only — the run continues with the remaining sources.

## `No pude descargar … (URLNoPermitida: …)`
The SSRF guard refused a SERP result: not `https`, a non-default port, a host resolving to a private/loopback/link-local/metadata IP, a redirect to one of those, more than 3 redirects, or not HTML. `plazo de 20s agotado` = the page was slower than the overall deadline. Warning only.

## Notion `Nota` sounds invented
It was: v1 stored the editor's free prose. Now Nota is factual code-built: `[words | sources | H1 fuera | conv_home]`.
