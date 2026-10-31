# DEPLOY_VPS (Ubuntu/Debian)

Run the agent as a dedicated, unprivileged user (never root):

```bash
sudo useradd --system --home /opt/notion-wp-blog-agent --shell /usr/sbin/nologin blogagent
sudo git clone https://github.com/miguelmartt/notion-wp-blog-agent.git /opt/notion-wp-blog-agent
cd /opt/notion-wp-blog-agent
sudo python3 -m venv venv && sudo ./venv/bin/pip install -r requirements.txt   # pinned versions
sudo cp .env.example .env            # fill in
sudo cp wp_credentials.example.json wp_credentials.json  # one entry per site, https:// keys only
sudo chown -R blogagent:blogagent /opt/notion-wp-blog-agent
sudo chmod 600 .env wp_credentials.json
# test once (needs one Pendiente row):
sudo -u blogagent ./venv/bin/python blog_automation.py
```

The cron lock is an `flock` on `.blog_automation.lock` next to the script, so the app directory must be writable by `blogagent`. The kernel releases it if a run crashes; `LOCK_FILE` is no longer read.

## WordPress per site (once)

1. **Dedicated user** for the agent (e.g. `automation`) with the **Author** or **Contributor** role, never Administrator or Editor. Neither role has `unfiltered_html`, so WordPress' own KSES filter runs on everything the agent posts — a second layer behind the agent's sanitizer. Contributors can only save drafts and pending posts, which is all the agent needs.
   Trade-off: Authors and Contributors can't assign another author. With `AUTHOR_MAP_JSON` the agent retries without `author`, so the draft keeps the automation user — change the author when you publish.
2. In `wp-config.php`, above "That's all, stop editing!":
   ```php
   define('DISALLOW_UNFILTERED_HTML', true);
   ```
   It removes `unfiltered_html` from every role (admins and editors included), so not even a leaked admin app password can store raw `<script>`.
3. `Users → automation → Application Passwords` → paste into `wp_credentials.json`. Site URLs (keys here and the Notion `Cliente` title) must be `https://` — the agent refuses plain `http`, where the app password would travel in clear.
4. Optional but recommended — expose Yoast meta to REST in `functions.php`:
```php
add_action('rest_api_init', function () {
  foreach (['_yoast_wpseo_title','_yoast_wpseo_metadesc'] as $k) {
    register_meta('post', $k, ['type'=>'string','single'=>true,'show_in_rest'=>true,'auth_callback'=>function(){return current_user_can('edit_posts');}]);
  }
});
```
Without it, meta is skipped gracefully and noted.

Tags: the agent only assigns tags that already exist (Authors and Contributors can't create terms anyway). Suggested new tags are listed in the Notion `Nota`; create them by hand if they fit.

## Log file

Readable only by the cron user and the `adm` group, rotated weekly:

```bash
sudo install -o blogagent -g adm -m 0640 /dev/null /var/log/notion-wp-blog.log
```

`/etc/logrotate.d/notion-wp-blog`:

```
/var/log/notion-wp-blog.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0640 blogagent adm
}
```

Secrets are redacted before they reach the log, but it still contains keywords, client URLs and SERP URLs.

## Cron

`sudo crontab -u blogagent -e`:

```cron
*/30 * * * * cd /opt/notion-wp-blog-agent && umask 027 && ./venv/bin/python blog_automation.py >> /var/log/notion-wp-blog.log 2>&1
```

Lock file prevents overlaps. Set `DRY_RUN=false` in `.env` for real publishing (still drafts only).

## Optional: egress firewall

SERP pages are only downloaded over `https` from hosts that resolve to public IPs, and every redirect is re-checked. There is a small residual window (DNS rebinding): `requests` resolves the name again when it connects. To close it, let the kernel refuse internal destinations for the cron user (keep the local DNS stub reachable):

```bash
sudo iptables -A OUTPUT -m owner --uid-owner blogagent -d 127.0.0.53 -p udp --dport 53 -j ACCEPT
sudo iptables -A OUTPUT -m owner --uid-owner blogagent -d 127.0.0.53 -p tcp --dport 53 -j ACCEPT
for net in 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do
  sudo iptables -A OUTPUT -m owner --uid-owner blogagent -d "$net" -j REJECT
done
sudo ip6tables -A OUTPUT -m owner --uid-owner blogagent -d ::1/128,fc00::/7,fe80::/10 -j REJECT
```

Persist the rules with your distro's tool (`iptables-persistent`, `nftables`).

## Costs

See ARCHITECTURE.md. Set an OpenAI usage limit ($5/mo is plenty for ~30 articles).
