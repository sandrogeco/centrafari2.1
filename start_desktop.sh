#!/bin/bash
# Script per avviare automaticamente VNC e noVNC

echo "🖥️ Avvio desktop remoto VNC..."

# Pulisci processi vecchi
pkill Xvnc 2>/dev/null || true
pkill websockify 2>/dev/null || true
rm -rf /tmp/.X* ~/.vnc/*.pid 2>/dev/null || true
sleep 1

# Avvia VNC server
vncserver :1 > /dev/null 2>&1
sleep 2

# Avvia noVNC
nohup websockify --web=/usr/share/novnc/ 6080 localhost:5901 > /tmp/websockify.log 2>&1 &
sleep 1

# Verifica che siano attivi
if pgrep -x Xvnc > /dev/null && pgrep -f websockify > /dev/null; then
    echo "✅ Desktop remoto avviato!"
    echo "   Apri la porta 6080 nel browser e vai su /vnc.html"
    echo "   Password: vscode"
else
    echo "❌ Errore nell'avvio del desktop"
fi
