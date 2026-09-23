# NOTION_SETUP (ES) — [English here](NOTION_SETUP.md)

Dos bases de datos en un workspace (formato de guía en `guides/style-guide.example.md`).

## Clientes — una fila por web

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| Cliente | Title | `https://example.com/` (URL exacta, es la clave) |
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
| Estado | Select | `Pendiente` → `Generado` / `Revisar` / `Publicado` (manual) |
| Enlace al borrador | URL | lo rellena el agente |
| Nota | Rich text | `[palabras | fuentes SERP | checks]` |

## Estados

- `Pendiente`: lo coge el cron.
- `Generado`: 1000-1400 palabras + checklist ok.
- `Revisar`: cupo, corto/largo, error publish o flag del editor. Lee Nota.
- `Publicado`: lo marcas tú al publicar en WordPress.
