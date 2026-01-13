#!/usr/bin/env python3
"""Debug script per verificare detection e colori in condizioni reali."""

import cv2
import numpy as np
import json
import sys
import os

sys.path.insert(0, '/home/user/centrafari')
import fari_detection
from funcs_misc import is_punto_ok, preprocess

# Carica config
with open('/home/user/centrafari/config.json', 'r') as f:
    config = json.load(f)

# Simula cache
cache = {
    'config': config,
    'stato_comunicazione': {
        'inclinazione': 0,
        'tipo_faro': 'anabbagliante'
    },
    'autoexp_ok': True
}

# Prova con un'immagine di test (crea immagine simulata)
print("="*60)
print("DEBUG: Sistema rilevamento colori a 3 livelli")
print("="*60)
print()

print(f"Config TOH: {config.get('TOH', 'N/A')}")
print(f"Config TOV: {config.get('TOV', 'N/A')}")
print()

# Crea immagine simulata con punti luminosi
img = np.zeros((320, 630), dtype=np.uint8)
center_x = 630 // 2
center_y = 320 // 2

# Simula pattern anabbagliante
# Linea sinistra (obliqua 15°)
for i in range(150):
    x = center_x - 80 + i
    y = int(center_y - i * np.tan(np.radians(15)))
    if 0 <= y < 320 and 0 <= x < 630:
        img[y, x] = 255

# Linea destra (obliqua -15°)
for i in range(150):
    x = center_x + i
    y = int(center_y - i * np.tan(np.radians(-15)))
    if 0 <= y < 320 and 0 <= x < 630:
        img[y, x] = 255

# Testa detection
print("Test 1: Pattern simulato al centro (dovrebbe essere VERDE)")
results = fari_detection.detect_anabbagliante(img, cache, 5, 40, 120, 1e-8, 1e-8, 1000)

print(f"  Punto rilevato: {results.get('punto')}")
print(f"  Linee rilevate: {len(results.get('linee', []))}")
print(f"  Angoli: {results.get('angoli')}")

if results.get('punto'):
    ptok = is_punto_ok(results['punto'], cache)
    print(f"  is_punto_ok: {ptok}")
    print(f"  STATUS: {ptok['status']} → ", end='')

    if ptok['status'] == 'ok':
        print("🟢 VERDE")
    elif ptok['status'] == 'warning':
        print("🟡 GIALLO")
    else:
        print("🔴 ROSSO")

    # Disegna risultati
    img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    img_result = fari_detection.draw_results(img_color, results, cache)

    # Verifica colore al punto
    px = results['punto']
    color = img_result[int(px[1]), int(px[0])]
    print(f"  Colore pixel al punto: BGR{list(color)}")

    cv2.imwrite('/tmp/debug_detection_center.jpg', img_result)
    print("  Immagine salvata in: /tmp/debug_detection_center.jpg")
else:
    print("  ❌ ERRORE: Punto non rilevato!")

print()
print("="*60)

# Test 2: Sposta il pattern fuori dal centro
print("Test 2: Pattern spostato +20px destra (dovrebbe essere GIALLO)")
img2 = np.zeros((320, 630), dtype=np.uint8)
offset = 20  # Sposta di 20px (TOH=10, quindi 10 < 20 < 20 → warning)

for i in range(150):
    x = center_x - 80 + i + offset
    y = int(center_y - i * np.tan(np.radians(15)))
    if 0 <= y < 320 and 0 <= x < 630:
        img2[y, x] = 255

for i in range(150):
    x = center_x + i + offset
    y = int(center_y - i * np.tan(np.radians(-15)))
    if 0 <= y < 320 and 0 <= x < 630:
        img2[y, x] = 255

results2 = fari_detection.detect_anabbagliante(img2, cache, 5, 40, 120, 1e-8, 1e-8, 1000)

print(f"  Punto rilevato: {results2.get('punto')}")

if results2.get('punto'):
    ptok2 = is_punto_ok(results2['punto'], cache)
    print(f"  is_punto_ok: {ptok2}")
    print(f"  STATUS: {ptok2['status']} → ", end='')

    if ptok2['status'] == 'ok':
        print("🟢 VERDE")
    elif ptok2['status'] == 'warning':
        print("🟡 GIALLO")
    else:
        print("🔴 ROSSO")

    img_color2 = cv2.cvtColor(img2, cv2.COLOR_GRAY2BGR)
    img_result2 = fari_detection.draw_results(img_color2, results2, cache)

    px2 = results2['punto']
    color2 = img_result2[int(px2[1]), int(px2[0])]
    print(f"  Colore pixel al punto: BGR{list(color2)}")

    cv2.imwrite('/tmp/debug_detection_offset.jpg', img_result2)
    print("  Immagine salvata in: /tmp/debug_detection_offset.jpg")
else:
    print("  ❌ ERRORE: Punto non rilevato!")

print()
print("="*60)
print("Debug completato!")
print()
print("CONCLUSIONE:")
print("  Se vedi 🟢 VERDE per test 1 e 🟡 GIALLO per test 2:")
print("  → Il sistema funziona CORRETTAMENTE")
print()
print("  Se NON funziona nel tuo test:")
print("  → Verifica che il punto venga rilevato correttamente")
print("  → Verifica i valori TOH e TOV in config.json")
print("  → Controlla che l'immagine /mnt/temp/frame.jpg esista")
print("="*60)
