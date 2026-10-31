# ARCHITECTURE (ES) — [English here](ARCHITECTURE.md)

Agente de un solo fichero (`blog_automation.py`). Stdlib + `requests` + `openai` + `python-dotenv` (versiones fijadas). Sin framework ni base de datos — el estado vive en Notion.

## Flujo

```
Notion Artículos (Pendiente)
 ├─ Notion Clientes → guía + cupo (si falla, no genera) · URL solo https
 ├─ Notion → En curso (antes de gastar nada)
 ├─ Serper top N (gl=es, hl=es) → descarga protegida contra SSRF (1,5 MB / 20 s)
 │                                → texto con html.parser, marcado como no fiable
 ├─ OpenAI redactor → JSON {titulo, meta_titulo, meta_descripcion, slug,
 │                           categoria_sugerida, excerpt, tags, html}
 ├─ OpenAI editor → impone checklist DE ESE cliente
 ├─ limpieza → home garantizado, bloque relacionados, slug único
 ├─ saneado → HTML por lista blanca (fuera <h1>, scripts, atributos, enlaces
 │            externos), título/extracto/meta a texto plano; si quita algo → Revisar
 ├─ WordPress REST POST /posts {status: draft, excerpt, tags existentes, categories, author}
 └─ Notion → Generado/Revisar + nota factual · aviso Telegram
```

## Decisiones clave (y cicatrices)

1. **Guías por cliente, jamás mezcladas.** La primera versión hardcodeó reglas de un cliente y contaminó la otra web. Ahora: "sigue la guía DE ESTE cliente al 100%" y la longitud vive en código (`1150` / `1000-1250`).
2. **SERP como base, no copia.** Snippets + ~2500 caracteres por fuente. Fallos de descarga (403) se saltan; `0 fuentes` = key/cuota Serper.
3. **Humano en el bucle.** Siempre `draft`. `Generado` = 1000-1400 + `ok`; si no `Revisar`. Fotos manuales por decisión.
4. **Notas factuales, no prosa.** La v1 guardaba el texto libre del editor y alucinaba. Ahora: `[palabras | fuentes | H1 fuera | conv_home]`.
5. **Los LLM no saben contar** (±15% normal). Objetivo 1150 para caer en 1300-1400. Topes físicos truncan el JSON, así que se acota por prompt + `max_completion_tokens=3500`.
6. **Modelos nuevos, params nuevos.** `gpt-5.x` rechaza `max_tokens` → `max_completion_tokens`.
7. **Roles WP importan.** El usuario de automatización es **Autor** o **Colaborador**: sin `unfiltered_html`, WordPress también filtra el contenido. A cambio no puede asignar otro autor (403): el código reintenta sin `author` y el borrador queda a su nombre. El mapeo de autor solo se aplica si el nombre coincide exactamente y es único.
8. **Yoast por REST necesita filtro** (`register_meta ... show_in_rest`). Sin él, reintento sin meta y aviso en Nota.
9. **DRY_RUN por defecto true.** Simula sin publicar.
10. **La salida del modelo no es fiable.** Acaba de leer tres webs cualesquiera: una prompt injection puede hacer que devuelva `<script>`, `onerror=`, `javascript:` o enlaces a cualquier sitio. El prompt lo pide por las buenas; el saneado por lista blanca lo impone. Si quita algo, la fila pasa a `Revisar` y la Nota dice qué.
11. **Las tags las decide una persona.** Crear términos desde la salida del modelo ensucia la taxonomía y exige más permisos. Solo se asignan tags existentes; las nuevas se sugieren en la Nota.
12. **`En curso` antes de gastar.** Si algo fallaba entre la llamada a OpenAI y la actualización de Notion, la fila seguía `Pendiente` y el siguiente cron generaba (y pagaba) un borrador duplicado.

## Costes (resumen, tabla en [COSTS.es.md](COSTS.es.md))

Por artículo ≈ 8000 in + 5000 out: `gpt-5.4` ≈ **$0.095** → 40 arts ≈ **$3.80/mes**, cualquier web.

## Seguridad

- Sin secretos en el repo (verificado por grep). `.env` + `wp_credentials.json` en gitignore.
- Mínimo privilegio: app passwords por web, integración Notion solo a 2 DBs, token Telegram en env.
- Parseo defensivo (`parse_json_robusto` + 1 reintento), timeouts 15-60s.
- XSS almacenado: todo lo que se publica pasa por `sanear_borrador` (y otra vez dentro de `wp_publish_draft`). Permitido: `p, h2, h3, ul, ol, li, strong, em, a`; en `a` solo `href`, `https` y al dominio del propio cliente (el resto queda como texto); cualquier otra etiqueta se quita conservando su texto (`script`, `style`, `iframe`, `svg`… se van con su contenido); el texto se vuelve a escapar y el HTML se reconstruye equilibrado. Título, extracto y meta de Yoast pasan a texto plano (sin etiquetas, sin `<`/`>`, sin caracteres de control, con tope).
- SSRF: páginas de la SERP solo por `https` y puerto 443, sin usuario en la URL, y solo si todas las IPs del host son públicas (fuera loopback, privadas, link-local, CGNAT, multicast, reservadas, sin especificar e IPv4 embebidas en IPv6). Redirecciones a mano (máx. 3), validando cada salto. Sin proxies del entorno y con User-Agent neutro. Riesgo residual: DNS rebinding entre la comprobación y la conexión; se cierra con un firewall de salida (DEPLOY_VPS.es.md).
- DoS: `stream=True`, tope de 1,5 MB, plazo total de 20 s vigilado por un hilo (un servidor que gotea bytes no bloquea la ejecución), texto con `html.parser` (sin regex con backtracking) y topes de etiquetas y anidamiento.
- Secretos: un formatter redacta cada línea del log (`bot<token>` de Telegram, `Bearer`, `sk-…`, `secret_…`/`ntn_…`, `api_key=`… y los valores literales de las claves configuradas y app passwords de WP). La `Nota` de Notion y Telegram solo reciben el *tipo* de excepción; el aviso de Telegram nunca lanza.
- Lock: `fcntl.flock` sobre `.blog_automation.lock` junto al script (no una ruta predecible en `/tmp`); lo suelta el kernel al salir o al reventar.
- WordPress recomendado: usuario dedicado Autor/Colaborador + `DISALLOW_UNFILTERED_HTML` + URLs solo https (DEPLOY_VPS.es.md).
