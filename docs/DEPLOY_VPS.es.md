# DEPLOY_VPS (ES) — [English here](DEPLOY_VPS.md)

Ejecuta el agente con un usuario dedicado y sin privilegios (nunca root):

```bash
sudo useradd --system --home /opt/notion-wp-blog-agent --shell /usr/sbin/nologin blogagent
sudo git clone https://github.com/miguelmartt/notion-wp-blog-agent.git /opt/notion-wp-blog-agent
cd /opt/notion-wp-blog-agent
sudo python3 -m venv venv && sudo ./venv/bin/pip install -r requirements.txt   # versiones fijadas
sudo cp .env.example .env            # rellenar
sudo cp wp_credentials.example.json wp_credentials.json  # una entrada por web, claves solo https://
sudo chown -R blogagent:blogagent /opt/notion-wp-blog-agent
sudo chmod 600 .env wp_credentials.json
sudo -u blogagent ./venv/bin/python blog_automation.py   # prueba (necesita una fila Pendiente)
```

El lock del cron es un `flock` sobre `.blog_automation.lock`, junto al script, así que la carpeta tiene que ser escribible por `blogagent`. Si una ejecución revienta, el kernel lo suelta solo; `LOCK_FILE` ya no se lee.

## WordPress por web (una vez)

1. **Usuario dedicado** para el agente (p. ej. `automatizacion`) con rol **Autor** o **Colaborador**, nunca Administrador ni Editor. Ninguno de los dos tiene `unfiltered_html`, así que el filtro KSES de WordPress pasa por todo lo que publica el agente: una segunda capa detrás de su propio saneado. Al Colaborador le basta para guardar borradores, que es lo único que hace el agente.
   Contrapartida: Autor y Colaborador no pueden asignar otro autor. Con `AUTHOR_MAP_JSON`, el agente reintenta sin `author` y el borrador queda a nombre del usuario de automatización: cámbialo al publicar.
2. En `wp-config.php`, encima de "¡Eso es todo, deja de editar!":
   ```php
   define('DISALLOW_UNFILTERED_HTML', true);
   ```
   Quita `unfiltered_html` a todos los roles (también administradores y editores): ni con una app password de admin filtrada se puede guardar un `<script>`.
3. `Usuarios → automatizacion → Contraseñas de aplicación` → pegar en `wp_credentials.json`. Las URLs de las webs (aquí y en el título `Cliente` de Notion) tienen que ser `https://`: el agente rechaza `http`, donde la app password viajaría en claro.
4. Recomendado — exponer meta Yoast a REST en `functions.php`:
```php
add_action('rest_api_init', function () {
  foreach (['_yoast_wpseo_title','_yoast_wpseo_metadesc'] as $k) {
    register_meta('post', $k, ['type'=>'string','single'=>true,'show_in_rest'=>true,'auth_callback'=>function(){return current_user_can('edit_posts');}]);
  }
});
```
Sin esto publica igual y lo marca en Nota.

Tags: el agente solo asigna tags que ya existen (Autor y Colaborador tampoco pueden crearlas). Las nuevas que sugiere el modelo van a la `Nota` de Notion; créalas a mano si encajan.

## Log

Solo lo leen el usuario del cron y el grupo `adm`, y rota cada semana:

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

Los secretos se redactan antes de llegar al log, pero sigue conteniendo keywords, URLs de clientes y de la SERP.

## Cron

`sudo crontab -u blogagent -e`:

```cron
*/30 * * * * cd /opt/notion-wp-blog-agent && umask 027 && ./venv/bin/python blog_automation.py >> /var/log/notion-wp-blog.log 2>&1
```

El lock evita solapes. `DRY_RUN=false` en `.env` para borradores reales (siempre draft).

## Opcional: firewall de salida

Las páginas de la SERP solo se descargan por `https` desde hosts que resuelven a IPs públicas, y cada redirección se vuelve a comprobar. Queda una ventana pequeña (DNS rebinding): `requests` vuelve a resolver el nombre al conectar. Para cerrarla, que sea el kernel quien rechace los destinos internos para el usuario del cron (dejando accesible el DNS local):

```bash
sudo iptables -A OUTPUT -m owner --uid-owner blogagent -d 127.0.0.53 -p udp --dport 53 -j ACCEPT
sudo iptables -A OUTPUT -m owner --uid-owner blogagent -d 127.0.0.53 -p tcp --dport 53 -j ACCEPT
for net in 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do
  sudo iptables -A OUTPUT -m owner --uid-owner blogagent -d "$net" -j REJECT
done
sudo ip6tables -A OUTPUT -m owner --uid-owner blogagent -d ::1/128,fc00::/7,fe80::/10 -j REJECT
```

Hazlas persistentes con la herramienta de tu distro (`iptables-persistent`, `nftables`).

## Costes

Ver [COSTS.es.md](COSTS.es.md). Pon límite de uso OpenAI ($5/mes sobra para ~30 artículos).
