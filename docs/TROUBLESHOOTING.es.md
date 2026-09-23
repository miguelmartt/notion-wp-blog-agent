# TROUBLESHOOTING (ES) — [English here](TROUBLESHOOTING.md)

## `SERP: 0 fuentes`
Serper no devolvió nada. Orden: ¿existe `SERPER_API_KEY` en `.env`? ¿longitud ~32? ¿Dashboard Serper → Logs (401 = key, 429 = cuota)? Pruébala en su Playground.
Sin SERP redacta fino — arregla la key, no lances en lote.

## `403 Forbidden` en `POST /wp-json/wp/v2/posts`
Casi siempre **autor**: un rol `Autor` no puede publicar a nombre de otro.
Fix: usuario automatización → **Editor**. El código reintenta sin autor para no morir.
Verifica: `GET /wp/v2/users/me` con la app password debe dar 200.

## Adjunto `posts.json` en Telegram
No es bug: tu texto de error contiene la URL `wp-json` y Telegram la previsualiza. Ignóralo, lee la línea `403/400`.

## `max_tokens is not supported, use max_completion_tokens`
`gpt-5.x` renombró el parámetro. El código usa `max_completion_tokens` (`OPENAI_MAX_TOKENS`, 3500).

## `JSONDecodeError: Unterminated string`
Tope de tokens cortó el JSON. Súbelo (3500 vale para ~1500 palabras) — el código reintenta y repara fences/comas vía `parse_json_robusto`.

## Se pasa de palabras (1500 → 1700)
Normal: estiman, no cuentan (±15%). Apunta **por debajo** (1150 para techo 1250). Perseguir el número exacto es inútil — asume banda ±150.

## `Meta Yoast no guardado`
WP responde 400 a `meta` sin exponerla por REST. Filtro `register_meta(..., show_in_rest)` en `functions.php` (ver DEPLOY_VPS). Sin él, publica igual y lo marca en Nota.

## `ModuleNotFoundError: dotenv`
Corriste el python del sistema: `source venv/bin/activate` primero.

## `Otra ejecución en curso (lock)`
Cron solapado, la segunda sale por diseño (`LOCK_FILE`). Alarga el intervalo, no quites el lock.

## `Cupo mensual alcanzado`
No es error: el cliente llegó a `Cupo/mes`. Fila a `Revisar` con `(usados/cupo)`.

## Descargas `403` (Mayo Clinic y cía.)
Bloquean bots. Aviso y sigue con el resto.

## Nota de Notion inventada
La v1 guardaba la prosa del editor. Ahora la Nota es factual desde código: `[palabras | fuentes | H1 fuera | conv_home]`.
