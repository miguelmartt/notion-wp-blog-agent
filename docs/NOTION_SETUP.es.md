# NOTION_SETUP (ES) — [English here](NOTION_SETUP.md)

Dos bases de datos en un workspace (formato de guía en `guides/style-guide.example.md`).

## Clientes — una fila por web

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| Cliente | Title | `https://example.com/` (URL exacta, es la clave; solo `https://`) |
| Cupo/mes | Number | `10` |
| Artículos | Relation → Artículos | auto |
| Contenido página | — | **guía de estilo completa pegada aquí** |

El agente lee toda la página como `guia_estilo`.

## Artículos — la cola de trabajo

| Propiedad | Tipo | Valores |
|---|---|---|
| Artículo | Title | etiqueta opcional |
| Cliente | Relation → Clientes | obligatorio |
| Keyword | Rich text | `cómo desatascar un fregadero` |
| Enfoque | Rich text | `ayuda práctica para inquilinos, sin jerga` |
| Estado | Select | `Pendiente` → `En curso` → `Generado` / `Revisar` / `Publicado` (manual) |
| Enlace al borrador | URL | lo rellena el agente |
| Nota | Rich text | `[palabras | fuentes SERP | checks]` |

## Estados

- `Pendiente`: lo coge el cron.
- `En curso`: lo pone el agente antes de gastar en Serper/OpenAI, para que el siguiente cron no vuelva a cogerlo. Si una ejecución muere a lo bruto (kill, falta de memoria) se queda aquí: mira el log, borra el borrador a medias si lo hay y vuelve a ponerlo en `Pendiente`. Notion crea la opción la primera vez.
- `Generado`: 1000-1400 palabras + checklist ok + el saneado no ha quitado nada.
- `Revisar`: cupo (o no se pudo comprobar), corto/largo, error publish, flag del editor o el saneado quitó algo (scripts, enlaces externos, atributos…). Lee Nota.
- `Publicado`: lo marcas tú al publicar en WordPress.
