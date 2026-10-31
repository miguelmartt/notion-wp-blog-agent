# NOTION_SETUP

Two databases in one Notion workspace (see `guides/style-guide.example.md` for the guide format).

## Clientes — one row per website

| Property | Type | Example |
|---|---|---|
| Cliente | Title | `https://example.com/` (exact site URL, used as key; `https://` only) |
| Cupo/mes | Number | `10` |
| Artículos | Relation → Artículos | auto |
| Page content | — | **full style guide pasted here** |

The agent reads the whole page content as `guia_estilo`.

## Artículos — the work queue

| Property | Type | Values |
|---|---|---|
| Artículo | Title | optional label |
| Cliente | Relation → Clientes | required |
| Keyword | Rich text | `how to reset a dishwasher` |
| Enfoque | Rich text | `practical help for renters, no jargon` |
| Estado | Select | `Pendiente` → `En curso` → `Generado` / `Revisar` / `Publicado` (manual) |
| Enlace al borrador | URL | filled by agent |
| Nota | Rich text | filled by agent: `[words | SERP sources | checks]` |

## States

- `Pendiente`: picked up by cron.
- `En curso`: set by the agent before it spends anything on Serper/OpenAI, so the next cron run doesn't pick the row again. If a run dies hard (killed, OOM) the row stays here: check the log, delete any half-made draft, set it back to `Pendiente` to retry. Notion creates the option on first use.
- `Generado`: 1000-1400 words + checklist ok + the sanitizer removed nothing.
- `Revisar`: quota hit or not checkable, short/long, publish error, editor flagged, or the sanitizer removed something (scripts, external links, attributes…). Read Nota.
- `Publicado`: set manually after you publish in WordPress.
