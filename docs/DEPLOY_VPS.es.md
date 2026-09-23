# DEPLOY_VPS (ES) — [English here](DEPLOY_VPS.md)

```bash
git clone https://github.com/miguelmartt/notion-wp-blog-agent.git /opt/notion-wp-blog-agent
cd /opt/notion-wp-blog-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # rellenar
cp wp_credentials.example.json wp_credentials.json  # una entrada por web
python blog_automation.py       # prueba (necesita una fila Pendiente)
```

## WordPress por web (una vez)

1. Usuario automatización con rol **Editor** (Autor no puede asignar otros autores).
2. `Usuarios → Automatizacion → Contraseñas de aplicación` → pegar en `wp_credentials.json`.
3. Recomendado — exponer meta Yoast a REST en `functions.php`:
```php
add_action('rest_api_init', function () {
  foreach (['_yoast_wpseo_title','_yoast_wpseo_metadesc'] as $k) {
    register_meta('post', $k, ['type'=>'string','single'=>true,'show_in_rest'=>true,'auth_callback'=>function(){return current_user_can('edit_posts');}]);
  }
});
```
Sin esto publica igual y lo marca en Nota.

## Cron

```cron
*/30 * * * * cd /opt/notion-wp-blog-agent && ./venv/bin/python blog_automation.py >> /var/log/notion-wp-blog.log 2>&1
```

El lock evita solapes. `DRY_RUN=false` en `.env` para borradores reales (siempre draft).

## Costes

Ver [COSTS.es.md](COSTS.es.md). Pon límite de uso OpenAI ($5/mes sobra para ~30 artículos).
