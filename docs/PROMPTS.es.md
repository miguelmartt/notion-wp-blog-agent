# PROMPTS (ES) — [English here](PROMPTS.md)

Dos llamadas con `response_format={"type": "json_object"}` y este contrato:

```json
{
  "titulo": "H1 para el campo título de WP",
  "meta_titulo": "<=60 caracteres",
  "meta_descripcion": "140-156 caracteres",
  "slug": "minusculas-con-guiones",
  "categoria_sugerida": "1-2 palabras",
  "excerpt": "1-2 frases, max 160",
  "tags": ["3-5 etiquetas"],
  "html": "<p>/<h2>/<h3>/<ul>/<ol>/<li>/<strong> solo, NUNCA <h1>"
}
```

## Redactor (`temperature=0.7`)

- System: redactor SEO senior, español (España). **Sigue la guía DE ESTE cliente al 100%, sin mezclar.** Sintetiza SERP, no copia, nada de IA genérica.
- User: guía completa + tono de posts propios + fuentes SERP + `keyword` + `enfoque` + `HOME_URL`.
- Enlaces: 1-2 internos inline con anchor natural + 1 conversión a HOME_URL.
- **La longitud manda desde código** (las guías discrepan): `OBJETIVO 1150, RANGO 1000-1250`. Los LLM se desvían ~15%, así que 1150 cae en ~1300-1400.

## Editor (`temperature=0.3`)

- Misma guía + conteo actual. Checklist DE ESE cliente: longitud, H2 pregunta + párrafo antes de lista, fórmulas prohibidas, frases de experiencia, anchors naturales, mención + CTA, sin `<h1>`, inline + home presentes.
- Devuelve `{"ok", "html_corregido", "nota"}`. Su `nota` libre **no se guarda** (alucinaba) — Nota en Notion la construye el código.

## Adaptar a un cliente nuevo

1. Pega su guía en su página de Notion — sin tocar prompts.
2. Solo cambia números si su banda difiere: writer + editor + ventana `Generado` en `procesar_articulo`.
3. Mantén el split: 0.7 redacta con variedad, 0.3 edita determinista.
