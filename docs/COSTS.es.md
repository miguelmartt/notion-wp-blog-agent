# COSTS (ES) — [English here](COSTS.md)

Por artículo (medido en producción): **~8000 input + ~5000 output tokens**.
1 búsqueda/article en Serper (despreciable). Mismo coste para cualquier web.

## Precios oficiales 2026 (por 1M tokens, verificar antes de comprar)

| Modelo | Input | Output | $/artículo | Notas |
|---|---|---|---|---|
| `gpt-4o` | $2.50 | $10.00 | ~$0.070 | default viejo, literal/corto |
| `gpt-5.2` | $1.75 | $14.00 | ~$0.084 | punto dulce antes del 5.4 |
| `gpt-5.4` (usado) | $2.50 | $15.00 | **~$0.095** | recomendado |
| `gpt-5.4 Pro` | $30.00 | $180.00 | ~$1.14 | 12× — no para volumen |
| `Claude Sonnet 4.6` (alt) | $3.00 | $15.00 | ~$0.10 | misma liga, mejor tono largo en español |

## Factura mensual por volumen

| Arts/mes | gpt-4o | gpt-5.4 (usado) | Sonnet | 5.4 Pro |
|---|---|---|---|---|
| 30 | $2.10 | $2.85 | $2.97 | $34.20 |
| 40 | $2.80 | **$3.80** | $3.96 | $45.60 |
| 50 | $3.50 | $4.75 | $4.95 | $57.00 |
| 60 | $4.20 | $5.70 | $5.94 | $68.40 |
| 70 | $4.90 | $6.65 | $6.93 | $79.80 |

**40 artículos, cualquier web: ~$3.80/mes con `gpt-5.4`.** Hasta 10 pruebas fallidas cuestan <$1.

## Que no se dispare

1. Una búsqueda/artículo (`SERP_NUM_RESULTADOS=3`).
2. `OPENAI_MAX_TOKENS=3500` acota desboques (muy bajo trunca el JSON).
3. Límite de uso OpenAI ($5/mes sobra para ~30) + vigila cuota Serper.
4. Prueba con `DRY_RUN=true` y de uno en uno, nunca en lote.
