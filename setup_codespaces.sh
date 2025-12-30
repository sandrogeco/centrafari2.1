#!/bin/bash
# Script per configurare l'ambiente Codespaces

echo "🔧 Installazione dipendenze di sistema..."
sudo apt-get update
sudo apt-get install -y python3-tk libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev

echo "📦 Installazione dipendenze Python..."
pip install -r requirements.txt

echo "✅ Setup completato!"
echo ""
echo "Verifica installazione:"
python3 -c "import cv2, scipy, tkinter; print('✅ OpenCV:', cv2.__version__); print('✅ SciPy:', scipy.__version__); print('✅ Tkinter: OK')"
