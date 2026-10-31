# ARCHITECTURE

Single-file agent (`blog_automation.py`). Stdlib + `requests` + `openai` + `python-dotenv` (pinned). No framework, no database — state lives in Notion, content lives in WordPress.

## Flow

```
Notion Artículos (Pendiente)
 ├─ Notion Clientes → guide text + quota (fails closed) · https-only site URL
 ├─ Notion → En curso (before any paid call)
 ├─ Serper top N (gl=es, hl=es) → SSRF-guarded download (1.5 MB / 20 s)
 │                                → html.parser text, marked untrusted
 ├─ OpenAI writer → JSON {titulo, meta_titulo, meta_descripcion, slug,
 │                         categoria_sugerida, excerpt, tags, html}
 ├─ OpenAI editor → enforces THIS client's checklist (length, H2, vocab,
 │                   links, CTA, no <h1>)
 ├─ cleanup → guarantee home link, append related box, unique slug (-2, -3…)
 ├─ sanitize → allowlist HTML (strips <h1>, scripts, attrs, external links),
 │             plain-text title/excerpt/meta; anything removed → Revisar
 ├─ WordPress REST POST /posts {status: draft, excerpt, existing tags, categories, author}
 └─ Notion → Generado/Revisar + factual note · Telegram ping
```

## Module map (inside the single file)

| Section | Functions | Notes |
|---|---|---|
| Config | env loading, `AUTHOR_MAP_JSON`, `DRY_RUN`, secret redaction (`redactar_secretos`, log formatter), `flock` lock | everything via env, zero hardcode |
| Notion | `notion_get_pending_articles`, `notion_client_fields`, `notion_count_usados_mes`, `notion_update_article` | paginated, quota via `created_time >= 1st of month` |
| HTML | `html_a_texto`, `sanear_html`, `sanear_borrador`, `texto_plano` | stdlib `html.parser`, no backtracking regex |
| SERP | `serper_buscar_top`, `validar_url_publica`, `descargar_texto_url`, `investigar_serp` | https + public IPs only, manual redirects, byte cap + deadline; failures are warnings, never fatal |
| AI | `generar_borrador`, `revisar_borrador`, `parse_json_robusto` | `response_format=json_object`, 1 retry on truncation |
| WordPress | `wp_fetch_*`, `wp_resolve_tags`, `wp_ensure_author`, `wp_publish_draft` | existing tags only; author on exact name match; retries without author/meta on 401/403/400 |
| Main | `procesar_articulo`, `main`, `acquire_lock` | per-article try/except → Revisar + Telegram (exception type only) |

## Key decisions (and scars behind them)

1. **Per-client guides, never mixed.** Early version hardcoded one client's rules globally and contaminated the other site. Now prompts say "follow THIS client's guide 100%" and length targets live in code (`1150` / `1000-1250`), tone/structure in the guide.
2. **SERP-grounded, not copied.** Snippets + ~2500 chars per source. Download failures (403 from Mayo Clinic et al.) are skipped; `0 fuentes` means Serper key/quota issue (see TROUBLESHOOTING).
3. **Human-in-the-loop.** `status=draft` always. `Generado` = 1000-1400 + `ok`; else `Revisar`. Photos stay manual by choice.
4. **Factual notes, not prose.** First version stored the editor's free text in Notion — it hallucinated ("no es real"). Now: `[words | sources | H1 fuera | conv_home]`.
5. **LLMs can't count.** Target 1150 lands 1300-1700 (±15%). Hard caps truncate JSON (`Unterminated string`), so we cap via prompt (`PROHIBIDO >1550`) + `max_completion_tokens=3500` + acceptance window instead of physical truncation.
6. **New-model params.** `gpt-5.x` rejects `max_tokens` → use `max_completion_tokens`. Kept compatible constant `OPENAI_MAX_TOKENS`.
7. **WP roles matter.** The automation user is an **Author** or **Contributor**: no `unfiltered_html`, so WordPress filters the content too. The price: it can't assign another author (403), so the code retries without `author` and the draft keeps the automation user. Author mapping only applies on an exact, unique name match.
8. **Yoast via REST needs a filter.** Without `register_meta(..., show_in_rest)` WP 400s on `meta`. Code retries without meta and flags it in Nota.
9. **DRY_RUN default true.** First runs simulate; flip to false only for real drafts.
10. **The model's output is untrusted.** It has just read three arbitrary web pages, so a prompt injection can make it emit `<script>`, `onerror=`, `javascript:` or links anywhere. Prompts ask nicely; the allowlist sanitizer enforces. Any removal flips the row to `Revisar` and lists what went.
11. **Tags are a human decision.** Creating terms from model output pollutes the taxonomy and needs extra capabilities. Only existing tags are assigned; new ones are suggested in the Nota.
12. **`En curso` before spending.** A crash between the OpenAI call and the Notion update used to leave the row `Pendiente`, so the next cron run generated (and paid for) a duplicate draft.

## Costs — summary (full table in COSTS.md)

Per article ≈ 8000 in + 5000 out tokens. `gpt-5.4` ($2.5/$15 per 1M) ≈ **$0.095/article** → 40 arts ≈ **$3.80/mo**, any site. `Pro` ≈ 12× more — unjustified for volume.

## Security

- No secrets in repo (grep-verified): `.env` + `wp_credentials.json` gitignored; only `.example` files committed. Rotate any key ever pasted in a screenshot.
- Least privilege: per-site WP app passwords, Notion integration scoped to 2 DBs, Telegram token in env, Serper key server-side only.
- Defensive parsing: fenced-JSON extraction, trailing-comma repair, one OpenAI retry; all external calls time-boxed (15-60s).
- Stored XSS: everything posted goes through `sanear_borrador` (re-applied inside `wp_publish_draft`). Allowed: `p, h2, h3, ul, ol, li, strong, em, a`; only `href` on `a`, `https` and the client's own domain (others are unwrapped to text); every other tag is dropped keeping its text (`script`, `style`, `iframe`, `svg`… go with their content); text re-escaped; output rebuilt from scratch and balanced. Title, excerpt and Yoast meta become plain text (no tags, no `<`/`>`, no control chars, capped).
- SSRF: SERP pages only over `https` on port 443, without userinfo, from hosts whose every resolved IP is public (loopback, private, link-local, CGNAT, multicast, reserved, unspecified, IPv4-mapped/6to4/NAT64/Teredo are refused). Redirects are followed by hand (max 3) and each hop is re-validated. No env proxies, neutral User-Agent. Residual risk: DNS rebinding between the check and the connection — close it with an egress firewall (DEPLOY_VPS.md).
- DoS: `stream=True`, 1.5 MB cap, 20 s overall deadline enforced by a watchdog thread (a slow-drip server can't pin the run), text extraction with `html.parser` (no backtracking regex), tag and nesting caps.
- Secrets: a log formatter redacts every line (Telegram `bot<token>`, `Bearer`, `sk-…`, `secret_…`/`ntn_…`, `api_key=`…, plus the literal configured keys and WP app passwords). Notion `Nota` and Telegram only ever get the exception *type*; the Telegram notifier never raises.
- Lock: `fcntl.flock` on `.blog_automation.lock` next to the script (not a predictable `/tmp` path); released by the kernel on exit or crash.
- Recommended WordPress setup: dedicated Author/Contributor user + `DISALLOW_UNFILTERED_HTML` + https-only URLs (DEPLOY_VPS.md).
