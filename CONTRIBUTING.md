# Contributing

PRs welcome. Keep it sanitized (no real hosts, tokens, IDs or client content) and bilingual (EN + ES README).

- Python 3.9+ (production runs 3.9: no newer syntax or stdlib APIs), `pip install -r requirements.txt`. No new dependencies without a good reason.
- Run tests: `python -m pytest tests/ -q` or `python -m unittest discover -s tests` (no credentials, network mocked; the `flock` tests only run on Linux/macOS).
- Anything that reaches WordPress goes through `sanear_borrador`; anything downloaded goes through `validar_url_publica`. Add a test with the payload when you touch either.
- Test end-to-end with `DRY_RUN=true` before touching WordPress.
