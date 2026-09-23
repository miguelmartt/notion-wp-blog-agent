# PROMPTS — writer + editor, and why they look like this

Both calls use `response_format={"type": "json_object"}` with this contract:

```json
{
  "titulo": "H1 for the WP title field",
  "meta_titulo": "<=60 chars",
  "meta_descripcion": "140-156 chars",
  "slug": "lowercase-with-dashes",
  "categoria_sugerida": "1-2 words",
  "excerpt": "1-2 sentences, max 160",
  "tags": ["3-5 short tags"],
  "html": "<p>/<h2>/<h3>/<ul>/<ol>/<li>/<strong> only, NO <h1>"
}
```

## Writer (`temperature=0.7`)

- System: senior SEO writer, Spanish (Spain). **Follow THIS client's guide 100%, never mix clients.** Synthesize SERP, never copy, never sound like generic AI.
- User: full client guide + own-post tone samples + SERP sources + `keyword` + `enfoque` + `HOME_URL`.
- Mandatory links: 1-2 inline internal with natural anchors + 1 conversion link to HOME_URL.
- **Length block wins over the guide** (guides disagree: 700-1000 vs 1200-2500): `OBJETIVO 1150, RANGO 1000-1250`. LLMs overshoot ~15%, so aiming 1150 lands ~1300-1400.
- Real lesson: demanding exact counts fails. We demand a target + hard range + let the editor trim.

## Editor (`temperature=0.3`)

- Same guide + current word count (`objetivo 1150, rango 1000-1250`).
- Checklist per THAT client: length, H2-as-question + paragraph-before-list, banned formulas, experience phrases, natural anchors, center mention + CTA, no `<h1>`, inline + home links present.
- Returns `{"ok", "html_corregido", "nota"}`. `ok` only if 1000-1400 + checklist. The free-text `nota` is **not** stored (it hallucinated) — Nota in Notion is built factually in code.

## Adapting to a new client

1. Paste their full guide in the Notion client page — no prompt edits needed.
2. Only touch code if their length band differs: change the two numbers in writer + editor + `Generado` window in `procesar_articulo`.
3. Keep `temperature` split: 0.7 drafts with variety, 0.3 edits deterministically.
