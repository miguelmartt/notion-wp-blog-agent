# TROUBLESHOOTING (ES) — [English here](TROUBLESHOOTING.md)

## `SERP: 0 fuentes`
Serper no devolvió nada. Orden: ¿existe `SERPER_API_KEY` en `.env`? ¿longitud ~32? ¿Dashboard Serper → Logs (401 = key, 429 = cuota)? Pruébala en su Playground.
Sin SERP redacta fino — arregla la key, no lances en lote.

## `403 Forbidden` en `POST /wp-json/wp/v2/posts`
Casi siempre **autor**: el usuario Autor/Colaborador recomendado no puede publicar a nombre de otro.
Esperado con `AUTHOR_MAP_JSON`: el código reintenta sin `author` y el borrador queda a nombre del usuario de automatización; cambia el autor al publicar. No lo subas a Editor/Administrador solo por esto (tendría `unfiltered_html` salvo con `DISALLOW_UNFILTERED_HTML`).
Verifica: `GET /wp/v2/users/me` con la app password debe dar 200.

## Telegram / Notion solo dicen `Error: ConnectionError`
Es así a propósito: el texto de una excepción puede llevar URLs con tokens (`/bot<TOKEN>/`), así que Notion y Telegram solo reciben el tipo. La traza completa, con los secretos redactados, está en el log del servidor.

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
Cron solapado, la segunda sale por diseño (`flock` sobre `.blog_automation.lock`, junto al script). Alarga el intervalo, no quites el lock. Una ejecución que revienta no lo deja bloqueado: lo suelta el kernel. `PermissionError` aquí = la carpeta no es escribible por el usuario del cron.

## Fila atascada en `En curso`
La ejecución murió a lo bruto (kill, falta de memoria) después de marcarla. Mira el log, borra el borrador a medias en WordPress si lo hay y vuelve a ponerla en `Pendiente`.

## `Revisar` con `Saneado, revisa el HTML: …` en la Nota
El saneado quitó algo antes de publicar: etiquetas fuera de la lista blanca (`script`, `iframe`, `img`, `div`…), atributos o enlaces que no eran `https` al dominio del cliente (se quedan como texto). Normalmente el modelo copió HTML de una página de la SERP: revisa el borrador antes de publicar. `URL de cliente no válida (solo https)` = el título `Cliente` de Notion no empieza por `https://`.

## `Tags sugeridas que no existen en WP`
No es error: el agente solo asigna tags que ya existen. Crea en WordPress las sugeridas que encajen y añádelas al borrador.

## `No pude comprobar cupo … no genero`
Notion falló al contar el uso del mes, así que no se generó nada (sin gasto en Serper/OpenAI). La fila pasa a `Revisar`; vuelve a ponerla en `Pendiente` para reintentar.

## `Cupo mensual alcanzado`
No es error: el cliente llegó a `Cupo/mes`. Fila a `Revisar` con `(usados/cupo)`.

## Descargas `403` (Mayo Clinic y cía.)
Bloquean bots. Aviso y sigue con el resto.

## `No pude descargar … (URLNoPermitida: …)`
La protección contra SSRF rechazó un resultado de la SERP: no es `https`, puerto no estándar, el host resuelve a una IP privada/loopback/link-local/de metadatos, redirige a una de ellas, más de 3 redirecciones o no es HTML. `plazo de 20s agotado` = la página tardó más que el plazo total. Solo es un aviso.

## Nota de Notion inventada
La v1 guardaba la prosa del editor. Ahora la Nota es factual desde código: `[palabras | fuentes | H1 fuera | conv_home]`.
