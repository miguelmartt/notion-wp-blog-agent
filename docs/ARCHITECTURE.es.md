# ARCHITECTURE (ES) — [English here](ARCHITECTURE.md)

Agente de un solo fichero (`blog_automation.py`, ~700 líneas). Stdlib + `requests` + `openai` + `python-dotenv`. Sin framework ni base de datos — el estado vive en Notion.

## Flujo

```
Notion Artículos (Pendiente)
 ├─ Notion Clientes → guía + cupo
 ├─ Serper top N (gl=es, hl=es) → descarga + limpieza
 ├─ OpenAI redactor → JSON {titulo, meta_titulo, meta_descripcion, slug,
 │                           categoria_sugerida, excerpt, tags, html}
 ├─ OpenAI editor → impone checklist DE ESE cliente
 ├─ limpieza → fuera <h1>, home garantizado, bloque relacionados, slug único
 ├─ WordPress REST POST /posts {status: draft, excerpt, tags, categories, author}
 └─ Notion → Generado/Revisar + nota factual · aviso Telegram
```

## Decisiones clave (y cicatrices)

1. **Guías por cliente, jamás mezcladas.** La primera versión hardcodeó reglas de un cliente y contaminó la otra web. Ahora: "sigue la guía DE ESTE cliente al 100%" y la longitud vive en código (`1150` / `1000-1250`).
2. **SERP como base, no copia.** Snippets + ~2500 caracteres por fuente. Fallos de descarga (403) se saltan; `0 fuentes` = key/cuota Serper.
3. **Humano en el bucle.** Siempre `draft`. `Generado` = 1000-1400 + `ok`; si no `Revisar`. Fotos manuales por decisión.
4. **Notas factuales, no prosa.** La v1 guardaba el texto libre del editor y alucinaba. Ahora: `[palabras | fuentes | H1 fuera | conv_home]`.
5. **Los LLM no saben contar** (±15% normal). Objetivo 1150 para caer en 1300-1400. Topes físicos truncan el JSON, así que se acota por prompt + `max_completion_tokens=3500`.
6. **Modelos nuevos, params nuevos.** `gpt-5.x` rechaza `max_tokens` → `max_completion_tokens`.
7. **Roles WP importan.** Un `Autor` no puede asignar otro autor → 403. Usuario automatización = **Editor**; el código reintenta sin autor para no tumbar la ejecución.
8. **Yoast por REST necesita filtro** (`register_meta ... show_in_rest`). Sin él, reintento sin meta y aviso en Nota.
9. **DRY_RUN por defecto true.** Simula sin publicar.

## Costes (resumen, tabla en [COSTS.es.md](COSTS.es.md))

Por artículo ≈ 8000 in + 5000 out: `gpt-5.4` ≈ **$0.095** → 40 arts ≈ **$3.80/mes**, cualquier web.

## Seguridad

- Sin secretos en el repo (verificado por grep). `.env` + `wp_credentials.json` en gitignore.
- Mínimo privilegio: app passwords por web, integración Notion solo a 2 DBs, token Telegram en env.
- Parseo defensivo (`parse_json_robusto` + 1 reintento), conteos por regex, timeouts 15-60s.
