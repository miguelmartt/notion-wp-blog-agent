# CHANGELOG

## [1.1.0] - 2026-10-31

Security hardening after an audit. Still Python 3.9+, no new dependencies.

### Security
- **Stored XSS:** the model's output (it has just read third-party pages) is sanitized right before posting by a stdlib (`html.parser`) allowlist: only `p, h2, h3, ul, ol, li, strong, em` and `a[href]`; links only `https` to the client's own domain (others become plain text); every other tag and attribute is dropped, `script`/`style`/`iframe`/`svg`… with their content; text re-escaped. Title, excerpt and Yoast meta become plain text with length caps. Anything removed → row goes to `Revisar` and the Nota lists it. `wp_publish_draft` re-applies the sanitizer.
- **SSRF:** SERP downloads are `https`-only (port 443, no userinfo), the host must resolve only to public IPs (loopback, private, link-local, CGNAT, multicast, reserved, unspecified and IPv4-in-IPv6 forms refused), redirects are followed by hand (max 3) re-validating every hop, env proxies ignored, neutral User-Agent. The downloaded text is marked as untrusted data in the prompt. Residual DNS-rebinding window documented, with an egress-firewall recipe.
- **DoS:** downloads use `stream=True` with a 1.5 MB cap and a 20 s overall deadline (watchdog thread, so slow-drip servers can't pin the run); the backtracking regex stripping (`<(script|style|…).*?>.*?</\1>`, `<h1.*?>.*?</h1>`) is replaced by `html.parser` text extraction with tag and nesting caps.
- **Secret leaks:** the Telegram notifier never raises and logs only the exception type (requests' errors contain `/bot<TOKEN>/`); Notion `Nota` and Telegram never get `str(e)`; new `redactar_secretos` helper (Telegram bot tokens, `Bearer`/`Basic`, `sk-…`, `secret_…`/`ntn_…`, `api_key=`-style pairs, configured keys and WP app passwords) wired into the log formatter, Notion notes and Telegram messages.
- **Lock:** the predictable `/tmp/blog_automation.lock` (`O_EXCL` + `atexit`) is replaced by `fcntl.flock` on `.blog_automation.lock` next to the script, released by the kernel even on a crash. `LOCK_FILE` is no longer read.
- **https-only client URLs:** a Notion `Cliente` that isn't `https://` is refused before any WordPress call.

### Changed
- New Notion state `En curso`, written before any Serper/OpenAI call, so a crash can't regenerate (and pay for) duplicate drafts every cron run.
- If the monthly quota can't be checked, nothing is generated (was: carry on).
- Author reassignment only on an exact, unique WordPress name match (was: first partial match). `AUTHOR_MAP_JSON` keys match the host or its subdomains, not any substring.
- Tags: only existing tags are assigned; the model's new suggestions go to the Notion Nota for a human (was: created automatically). `wp_ensure_tags` → `wp_resolve_tags`.
- `requirements.txt` pinned to the versions running in production: `requests==2.32.5`, `python-dotenv==1.2.1`, `openai==2.48.0`.
- Prompts list the allowed tags (`em` and `a` added) and forbid attributes and external links.

### Docs
- Recommend a dedicated WordPress user with the Author or Contributor role (no `unfiltered_html`) and `define('DISALLOW_UNFILTERED_HTML', true)`; run cron as an unprivileged user; log file `0640` + logrotate; optional egress firewall.

### Tests
- Offline suite (network mocked, no credentials): sanitizer (payload corpus + idempotence), SSRF/redirects/caps/deadline, secret redaction, lock, quota/`En curso`/tags/author flow. `python -m pytest tests/ -q` or `python -m unittest discover -s tests`.

## [1.0.0] - 2026-09-23
- Initial public release (MIT).
- Notion queue + per-client guides + quota.
- SERP research (Serper) + writer/editor passes.
- WordPress drafts: SEO meta, excerpt, tags, categories, internal + conversion links, unique slugs, author mapping.
- Telegram pings, file lock, DRY_RUN, factual Notion notes.
