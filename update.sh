#!/bin/bash
set -euo pipefail

ARCHIVE_PATH="${1:-}"
INSTALL_DIR="/home/pi/Applications/MW28912"

if [ -z "$ARCHIVE_PATH" ]; then
  echo "Uso: $0 <path_archivio>" >&2
  exit 1
fi

if [ ! -f "$ARCHIVE_PATH" ]; then
  echo "Archivio non trovato: $ARCHIVE_PATH" >&2
  exit 1
fi

# ------------------------------------------------------------------------
# Termina processi MW

echo "Terminazione processi MW..."
sudo pkill -9 -x "mw28912" 2>/dev/null || true
sudo pkill -9 -f "MW28912\.py" 2>/dev/null || true
sudo pkill -9 -x "usb_video_captu" 2>/dev/null || true

sleep 2

# ------------------------------------------------------------------------
# Estrazione

echo "Estrazione in $INSTALL_DIR..."
sudo tar -xzf "$ARCHIVE_PATH" \
  --overwrite \
  --preserve-permissions \
  --same-owner \
  -C "$INSTALL_DIR"

rm -rf /tmp/mw_update
echo "Installazione completata."

# ------------------------------------------------------------------------
# Reboot

echo "Reboot in 3 secondi..."
sleep 3
sudo reboot
