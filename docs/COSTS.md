# COSTS — what the API bill really looks like

Assumptions per article (measured in production): **~8000 input + ~5000 output tokens**
(input = client guide + 3 own posts + 3 SERP pages + brief; output = writer draft + editor rewrite).
1 search/article on Serper (negligible). Same cost whatever the website.

## Official 2026 prices (per 1M tokens, verify before buying)

| Model | Input | Output | $/article | Notes |
|---|---|---|---|---|
| `gpt-4o` | $2.50 | $10.00 | ~$0.070 | old default, literal/short output |
| `gpt-5.2` | $1.75 | $14.00 | ~$0.084 | sweet spot before 5.4 |
| `gpt-5.4` (used) | $2.50 | $15.00 | **~$0.095** | recommended: instruction-following + structure |
| `gpt-5.4 Pro` | $30.00 | $180.00 | ~$1.14 | 12× the price — not for volume |
| `Claude Sonnet 4.6` (alt) | $3.00 | $15.00 | ~$0.10 | same league, best long-form tone in Spanish |

Math: `8000/1M × input + 5000/1M × output`.

## Monthly bill by volume

| Articles/mo | gpt-4o (old) | gpt-5.4 (used) | Sonnet alt | 5.4 Pro |
|---|---|---|---|---|
| 30 | $2.10 | $2.85 | $2.97 | $34.20 |
| 40 | $2.80 | **$3.80** | $3.96 | $45.60 |
| 50 | $3.50 | $4.75 | $4.95 | $57.00 |
| 60 | $4.20 | $5.70 | $5.94 | $68.40 |
| 70 | $4.90 | $6.65 | $6.93 | $79.80 |

**40 articles, any site: ~$3.80/mo on `gpt-5.4`.** (€ ≈ $.) Even 10 failed test runs cost <$1.

## Keep it cheap

1. One search/article (`SERP_NUM_RESULTADOS=3`). More sources = linear input cost.
2. `OPENAI_MAX_TOKENS=3500` caps runaway outputs (too low truncates JSON — see TROUBLESHOOTING).
3. Set an OpenAI usage limit ($5/mo covers ~30 articles) + watch Serper Dashboard quota.
4. Test with `DRY_RUN=true` (still calls OpenAI/SERP) but one `Pendiente` row at a time — never bulk-test.
