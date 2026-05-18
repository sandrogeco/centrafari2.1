#!/bin/bash
set -euo pipefail

SERVER="https://topauto.syel-service.it/aggiornamenti"
USERNAME_MACCHINA="1000abcd"
PASSWORD_MACCHINA="123456"
INSTALL_DIR="/home/pi/Applications/MW28912"
REFRESH_TOKEN_FILE="$INSTALL_DIR/.refresh_token"
TMP_DIR="/tmp/mw_update"

# ------------------------------------------------------------------------
# Auth

do_login() {
  local token
  token="$(curl -fsSL -X POST "$SERVER/auth_machine" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "username=$USERNAME_MACCHINA" \
    -d "password=$PASSWORD_MACCHINA")"
  if [[ "$token" != eyJ* ]]; then
    echo "Autenticazione fallita (login)" >&2; exit 1
  fi
  echo "$token" > "$REFRESH_TOKEN_FILE"
  echo "$token"
}

do_freshen() {
  local token
  token="$(curl -fsSL -X POST "$SERVER/freshen_token" --data "$1")"
  if [[ "$token" != eyJ* ]]; then return 1; fi
  echo "$token"
}

if [ -f "$REFRESH_TOKEN_FILE" ]; then
  REFRESH_TOKEN="$(cat "$REFRESH_TOKEN_FILE")"
else
  echo "Nessun refresh token, eseguo login..."
  REFRESH_TOKEN="$(do_login)"
fi

ACCESS_TOKEN="$(do_freshen "$REFRESH_TOKEN")" || {
  echo "Refresh scaduto, eseguo login..."
  REFRESH_TOKEN="$(do_login)"
  ACCESS_TOKEN="$(do_freshen "$REFRESH_TOKEN")"
}

echo "Autenticazione OK."

# ------------------------------------------------------------------------
# Check aggiornamento

presente="$(curl -fsSL "$SERVER/check?format=txt&fields=presente" \
  -H "Authorization: Bearer $ACCESS_TOKEN")"

if [ "$presente" != "True" ]; then
  echo "Nessun aggiornamento disponibile."
  exit 0
fi

echo "Aggiornamento disponibile."

IFS=',' read -r script script_md5 archive archive_md5 <<< \
  "$(curl -fsSL "$SERVER/check?format=txt&fields=script,script_md5,archive,archive_md5&sep=," \
    -H "Authorization: Bearer $ACCESS_TOKEN")"

echo "Script:  $script"
echo "Archive: $archive"

# ------------------------------------------------------------------------
# Download

mkdir -p "$TMP_DIR"

verify_md5() {
  local file="$1" expected="$2"
  if [ -n "$expected" ] && [ "$expected" != "None" ]; then
    local actual
    actual="$(md5sum "$file" | cut -d' ' -f1)"
    if [ "$actual" != "$expected" ]; then
      echo "MD5 non valido per $file" >&2; exit 1
    fi
    echo "MD5 OK: $(basename "$file")"
  fi
}

echo "Download script..."
curl -f --max-time 60 --progress-bar "$SERVER/download?file=$script" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o "$TMP_DIR/$script"
verify_md5 "$TMP_DIR/$script" "$script_md5"

ARCHIVE_PATH=""
if [ -n "$archive" ] && [ "$archive" != "None" ]; then
  echo "Download archivio..."
  curl -f --max-time 600 --progress-bar "$SERVER/download?file=$archive" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -o "$TMP_DIR/$archive"
  verify_md5 "$TMP_DIR/$archive" "$archive_md5"
  ARCHIVE_PATH="$TMP_DIR/$archive"
fi

# ------------------------------------------------------------------------
# Avvia installazione

echo "Avvio installazione..."
chmod +x "$INSTALL_DIR/update.sh"
exec "$INSTALL_DIR/update.sh" "$ARCHIVE_PATH"
