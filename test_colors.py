#!/usr/bin/env python3
"""Test visivo per verificare il sistema a 3 colori."""

import cv2
import numpy as np
import sys
sys.path.insert(0, '/home/user/centrafari')

import fari_detection
from funcs_misc import is_punto_ok

# Crea immagine di test
img = np.zeros((320, 630, 3), dtype=np.uint8)

# Simula cache
cache = {
    'config': {
        'width': 630,
        'height': 320,
        'TOH': 10,
        'TOV': 10
    },
    'stato_comunicazione': {
        'incl': 0
    }
}

center_x = 630 // 2  # 315
center_y = 320 // 2  # 160

# Disegna croce di riferimento
cv2.line(img, (center_x - 10, center_y), (center_x + 10, center_y), (100, 100, 100), 1)
cv2.line(img, (center_x, center_y - 10), (center_x, center_y + 10), (100, 100, 100), 1)

# Test 3 punti con 3 colori diversi
test_points = [
    ((center_x + 5, center_y + 5), "OK (verde)"),      # Dentro
    ((center_x + 15, center_y + 15), "WARNING (giallo)"),  # Poco fuori
    ((center_x + 25, center_y + 25), "ERROR (rosso)")     # Molto fuori
]

for i, (punto, label) in enumerate(test_points):
    # Simula results
    results = {
        'tipo': 'anabbagliante',
        'punto': punto,
        'linee': [],
        'contorni': [],
        'punti_fitted': [],
        'angoli': (0, 0, 0)
    }

    # Usa draw_results
    img_copy = img.copy()
    img_result = fari_detection.draw_results(img_copy, results, cache)

    # Verifica is_punto_ok
    ptok = is_punto_ok(punto, cache)

    # Aggiungi testo
    cv2.putText(img_result, f"{label} - Status: {ptok['status']}",
                (10, 30 + i*20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Salva immagine
    filename = f"/tmp/test_color_{i+1}_{ptok['status']}.jpg"
    cv2.imwrite(filename, img_result)
    print(f"Salvato: {filename}")
    print(f"  Punto: {punto}, Status: {ptok['status']}, Details: {ptok}")

    # Verifica colore del pixel al punto
    px_color = img_result[int(punto[1]), int(punto[0])]
    print(f"  Colore pixel BGR: {px_color}")
    print()

print("Test completato! Controlla le immagini in /tmp/")
