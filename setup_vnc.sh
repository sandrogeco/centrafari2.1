#!/bin/bash
# Script completo per configurare desktop remoto VNC in Codespaces

set -e

echo "🖥️  Setup Desktop Remoto VNC - Iniziato"
echo "========================================="
echo ""

# 1. Pulizia processi esistenti
echo "🧹 Pulizia processi VNC esistenti..."
pkill Xvnc 2>/dev/null || true
pkill websockify 2>/dev/null || true
pkill fluxbox 2>/dev/null || true
rm -rf ~/.vnc/*.pid 2>/dev/null || true
sleep 2

# 2. Installazione pacchetti
echo "📦 Installazione pacchetti necessari..."
sudo apt-get update -qq
sudo apt-get install -y \
  tigervnc-standalone-server \
  tigervnc-common \
  novnc \
  python3-websockify \
  python3-numpy \
  dbus-x11 \
  fluxbox \
  xterm \
  x11-utils \
  fonts-dejavu \
  > /dev/null 2>&1

# 3. Configurazione VNC
echo "🔧 Configurazione VNC..."
mkdir -p ~/.vnc

# Password VNC
echo "vscode" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Script di avvio X
cat > ~/.vnc/xstartup << 'XSTARTUP_EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
exec fluxbox &
XSTARTUP_EOF
chmod +x ~/.vnc/xstartup

# Configurazione VNC server
cat > ~/.vnc/config << 'CONFIG_EOF'
geometry=1920x1080
depth=24
localhost=no
alwaysshared
CONFIG_EOF

# 4. Avvio VNC Server
echo "🚀 Avvio VNC Server..."
vncserver :1 -kill 2>/dev/null || true
sleep 1
vncserver :1
sleep 3

# Verifica VNC
if ! pgrep -x Xvnc > /dev/null; then
    echo "❌ Errore: VNC Server non si è avviato"
    exit 1
fi

# 5. Avvio noVNC
echo "🌐 Avvio noVNC web server..."
nohup websockify --web=/usr/share/novnc/ 6080 localhost:5901 > /tmp/websockify.log 2>&1 &
sleep 2

# Verifica noVNC
if ! pgrep -f websockify > /dev/null; then
    echo "❌ Errore: noVNC non si è avviato"
    exit 1
fi

echo ""
echo "✅ Desktop Remoto Configurato!"
echo "======================================"
echo ""
echo "📍 Prossimi passi:"
echo ""
echo "1. Vai alla tab PORTE in VS Code (in basso)"
echo "2. Se non vedi la porta 6080, clicca 'Inoltra una porta' e inserisci: 6080"
echo "3. Clicca sull'icona del globo 🌐 accanto alla porta 6080"
echo "4. Nell'URL che si apre, aggiungi '/vnc.html' alla fine"
echo "   Esempio: https://xxx-6080.app.github.dev/vnc.html"
echo "5. Clicca 'Connect'"
echo "6. Password: vscode"
echo ""
echo "📝 Nel desktop remoto:"
echo "   - Click destro sullo sfondo → Terminal"
echo "   - Esegui: cd /workspaces/centrafari && python3 MW28912.py"
echo ""
echo "🔍 Verifica servizi:"
ps aux | grep -E 'Xvnc|websockify' | grep -v grep
echo ""
echo "✅ Tutto pronto! Apri il browser sulla porta 6080/vnc.html"
echo ""
