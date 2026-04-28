#!/bin/bash
set -euo pipefail

HOSTS_FILE="/etc/hosts"
HTTPD_CONF="/etc/apache2/httpd.conf"
ENV_NOTES_CONF="/etc/apache2/other/env-notes.conf"
APACHE_PLIST="/System/Library/LaunchDaemons/org.apache.httpd.plist"
STAMP="$(date +%Y%m%d%H%M%S)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "This installer must run as root."
  exit 1
fi

echo "Configuring env-notes host entries..."
if ! grep -Eq '(^|[[:space:]])env-notes([[:space:]]|$)' "$HOSTS_FILE"; then
  cp -p "$HOSTS_FILE" "${HOSTS_FILE}.env-notes.${STAMP}.bak"
  printf '\n# Env Notes local shortcuts\n127.0.0.1  env-notes notes env_notes\n' >> "$HOSTS_FILE"
fi

echo "Enabling Apache proxy modules..."
cp -p "$HTTPD_CONF" "${HTTPD_CONF}.env-notes.${STAMP}.bak"
/usr/bin/sed -i '' \
  -e 's/^#LoadModule proxy_module libexec\/apache2\/mod_proxy.so/LoadModule proxy_module libexec\/apache2\/mod_proxy.so/' \
  -e 's/^#LoadModule proxy_http_module libexec\/apache2\/mod_proxy_http.so/LoadModule proxy_http_module libexec\/apache2\/mod_proxy_http.so/' \
  "$HTTPD_CONF"

echo "Writing Apache virtual host..."
if [[ -f "$ENV_NOTES_CONF" ]]; then
  cp -p "$ENV_NOTES_CONF" "${ENV_NOTES_CONF}.env-notes.${STAMP}.bak"
fi
cat > "$ENV_NOTES_CONF" <<'EOF'
<VirtualHost *:80>
    ServerName env-notes
    ServerAlias notes
    ServerAlias env_notes

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:9490/
    ProxyPassReverse / http://127.0.0.1:9490/

    ErrorLog "/private/var/log/apache2/env-notes-error.log"
    CustomLog "/private/var/log/apache2/env-notes-access.log" common
</VirtualHost>
EOF

echo "Validating Apache configuration..."
/usr/sbin/apachectl configtest

echo "Enabling Apache launch daemon..."
if /bin/launchctl print system/org.apache.httpd >/dev/null 2>&1; then
  /usr/sbin/apachectl restart
else
  /bin/launchctl load -w "$APACHE_PLIST" || true
  /usr/sbin/apachectl restart
fi

echo "Done. Open http://env-notes/ (Safari-friendly)"
