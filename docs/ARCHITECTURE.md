# ARCHITECTURE

Single-file agent (`blog_automation.py`, ~700 lines). Stdlib + `requests` + `openai` + `python-dotenv`. No framework, no database — state lives in Notion, content lives in WordPress.

## Flow

```
Notion Artículos (Pendiente)
 ├─ Notion Clientes → guide text + quota
 ├─ Serper top N (gl=es, hl=es) → download + strip scripts/nav/footer
 ├─ OpenAI writer → JSON {titulo, meta_titulo, meta_descripcion, slug,
 │                         categoria_sugerida, excerpt, tags, html}
 ├─ OpenAI editor → enforces THIS client's checklist (length, H2, vocab,
 │                   links, CTA, no <h1>)
 ├─ cleanup → strip <h1>, guarantee home link, append related box,
 │             unique slug (-2, -3…)
 ├─ WordPress REST POST /posts {status: draft, excerpt, tags, categories, author}
 └─ Notion → Generado/Revisar + factual note · Telegram ping
```

## Module map (inside the single file)

| Section | Functions | Notes |
|---|---|---|
| Config | env loading, `AUTHOR_MAP_JSON`, `DRY_RUN`, lock | everything via env, zero hardcode |
| Notion | `notion_get_pending_articles`, `notion_client_fields`, `notion_count_usados_mes`, `notion_update_article` | paginated, quota via `created_time >= 1st of month` |
| SERP | `serper_buscar_top`, `descargar_texto_url`, `investigar_serp` | failures are warnings, never fatal |
| AI | `generar_borrador`, `revisar_borrador`, `parse_json_robusto` | `response_format=json_object`, 1 retry on truncation |
| WordPress | `wp_fetch_*`, `wp_ensure_tags`, `wp_ensure_author`, `wp_publish_draft` | retries without author/meta on 401/403/400 |
| Main | `procesar_articulo`, `main`, `acquire_lock` | per-article try/except → Revisar + Telegram |

## Key decisions (and scars behind them)

1. **Per-client guides, never mixed.** Early version hardcoded one client's rules globally and contaminated the other site. Now prompts say "follow THIS client's guide 100%" and length targets live in code (`1150` / `1000-1250`), tone/structure in the guide.
2. **SERP-grounded, not copied.** Snippets + ~2500 chars per source. Download failures (403 from Mayo Clinic et al.) are skipped; `0 fuentes` means Serper key/quota issue (see TROUBLESHOOTING).
3. **Human-in-the-loop.** `status=draft` always. `Generado` = 1000-1400 + `ok`; else `Revisar`. Photos stay manual by choice.
4. **Factual notes, not prose.** First version stored the editor's free text in Notion — it hallucinated ("no es real"). Now: `[words | sources | H1 fuera | conv_home]`.
5. **LLMs can't count.** Target 1150 lands 1300-1700 (±15%). Hard caps truncate JSON (`Unterminated string`), so we cap via prompt (`PROHIBIDO >1550`) + `max_completion_tokens=3500` + acceptance window instead of physical truncation.
6. **New-model params.** `gpt-5.x` rejects `max_tokens` → use `max_completion_tokens`. Kept compatible constant `OPENAI_MAX_TOKENS`.
7. **WP roles matter.** An `Author` user cannot assign another author → 403 on publish. Automation user must be **Editor**; code still retries without author so one bad mapping never kills the run.
8. **Yoast via REST needs a filter.** Without `register_meta(..., show_in_rest)` WP 400s on `meta`. Code retries without meta and flags it in Nota.
9. **DRY_RUN default true.** First runs simulate; flip to false only for real drafts.

## Costs — summary (full table in COSTS.md)

Per article ≈ 8000 in + 5000 out tokens. `gpt-5.4` ($2.5/$15 per 1M) ≈ **$0.095/article** → 40 arts ≈ **$3.80/mo**, any site. `Pro` ≈ 12× more — unjustified for volume.

## Security

- No secrets in repo (grep-verified): `.env` + `wp_credentials.json` gitignored; only `.example` files committed. Rotate any key ever pasted in a screenshot.
- Least privilege: per-site WP app passwords, Notion integration scoped to 2 DBs, Telegram token in env, Serper key server-side only.
- Defensive parsing: fenced-JSON extraction, trailing-comma repair, one OpenAI retry; word counts by regex; all external calls time-boxed (15-60s).
