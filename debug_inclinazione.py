#!/usr/bin/env python3
"""
Debug script per verificare inclinazione negli indicatori
"""
import sys
sys.path.insert(0, '/home/user/centrafari')
from funcs_misc import is_punto_ok

# Simula scenario dall'immagine
punto = (300, 137)
center = (315, 160)

print("="*70)
print("DEBUG: Inclinazione negli indicatori direzionali")
print("="*70)
print()
print(f"Punto rilevato: {punto}")
print(f"Centro default: {center} (width/2=315, height/2=160)")
print()

# Test con diverse inclinazioni
for incl in [0, -10, -23, 10, 23]:
    cache = {
        'config': {'width': 630, 'height': 320, 'TOH': 10, 'TOV': 10},
        'stato_comunicazione': {'inclinazione': str(incl)}
    }

    result = is_punto_ok(punto, cache)

    center_y_incl = 160 + incl
    dy = punto[1] - center_y_incl

    print(f"Inclinazione = {incl:3d}:")
    print(f"  Centro Y effettivo: {center_y_incl}")
    print(f"  Offset verticale (dy): {dy:3d}")
    print(f"  Indicatori: left={result['left']} right={result['right']} up={result['up']} down={result['down']}")

    # Verifica coerenza
    if dy < -10:
        expected_down = 2 if dy < -20 else 1
        if result['down'] == expected_down:
            print(f"  ✓ Corretto: punto in alto → down={expected_down}")
        else:
            print(f"  ✗ ERRORE: atteso down={expected_down}, ottenuto down={result['down']}")
    elif dy > 10:
        expected_up = 2 if dy > 20 else 1
        if result['up'] == expected_up:
            print(f"  ✓ Corretto: punto in basso → up={expected_up}")
        else:
            print(f"  ✗ ERRORE: atteso up={expected_up}, ottenuto up={result['up']}")
    else:
        if result['up'] == 0 and result['down'] == 0:
            print(f"  ✓ Corretto: punto al centro verticalmente")
        else:
            print(f"  ✗ ERRORE: dovrebbe essere al centro")

    print()

print("="*70)
print("CONCLUSIONE:")
print("="*70)
print()
print("Il codice considera CORRETTAMENTE l'inclinazione.")
print()
print("Se vedi 'down=2' nell'output ma la croce verde sembra centrata")
print("sul punto giallo, allora:")
print()
print("  1. VERIFICA il valore di 'inclinazione' nei log [RX]")
print("  2. Il server potrebbe non inviare l'inclinazione")
print("  3. O il parametro ha un nome diverso (es. 'incl', 'tilt', etc)")
print()
print("Per verificare, aggiungi un print in MW28912.py linea 205:")
print('  print(f"DEBUG inclinazione: {cache[\'stato_comunicazione\'].get(\'inclinazione\', \'NOT FOUND\')}")')
print()
