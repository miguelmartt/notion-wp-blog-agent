# DEPLOY_VPS (Ubuntu/Debian)

```bash
git clone https://github.com/miguelmartt/notion-wp-blog-agent.git /opt/notion-wp-blog-agent
cd /opt/notion-wp-blog-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in
cp wp_credentials.example.json wp_credentials.json  # one entry per site
# test once:
python blog_automation.py
```

## WordPress per site (once)

1. User for automation with **Editor** role (Authors can't assign other authors).
2. `Users → Automation → Application Passwords` → paste into `wp_credentials.json`.
3. Optional but recommended — expose Yoast meta to REST in `functions.php`:
```php
add_action('rest_api_init', function () {
  foreach (['_yoast_wpseo_title','_yoast_wpseo_metadesc'] as $k) {
    register_meta('post', $k, ['type'=>'string','single'=>true,'show_in_rest'=>true,'auth_callback'=>function(){return current_user_can('edit_posts');}]);
  }
});
```
Without it, meta is skipped gracefully and noted.

## Cron

```cron
*/30 * * * * cd /opt/notion-wp-blog-agent && ./venv/bin/python blog_automation.py >> /var/log/notion-wp-blog.log 2>&1
```

Lock file prevents overlaps. Set `DRY_RUN=false` in `.env` for real publishing (still drafts only).

## Costs

See ARCHITECTURE.md. Set an OpenAI usage limit ($5/mo is plenty for ~30 articles).
