#!/bin/bash
set -euo pipefail

INSTALL_DIR="/home/pi/Applications/MW28912"

cd "$INSTALL_DIR"
tar -czf /tmp/update.tar.gz .
cp "$INSTALL_DIR/update.sh" /tmp/update.sh
echo "Creati /tmp/update.tar.gz e /tmp/update.sh"
