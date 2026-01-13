#!/usr/bin/env python3
"""
Script di test per verificare TOH/TOV da comunicazione.

Esempio di risposta dal server:
"croce 1; run 1; tipo_faro anabbagliante; TOH 30; TOV 20; inclinazione 5;"
"""

import sys
sys.path.insert(0, '/home/user/centrafari')
from comms import decode_cmd1
from funcs_misc import is_punto_ok

print("="*70)
print("TEST: TOH e TOV da comunicazione vs config")
print("="*70)
print()

# Simula risposta server
server_responses = [
    "croce 1; run 1; tipo_faro anabbagliante;",  # Senza TOH/TOV
    "croce 1; run 1; tipo_faro anabbagliante; TOH 30; TOV 20;",  # Con TOH/TOV
    "croce 1; run 1; tipo_faro fendinebbia; TOH 50; TOV 10; inclinazione 5;",  # TOH/TOV + inclinazione
]

for i, resp in enumerate(server_responses, 1):
    print(f"Test {i}:")
    print(f"  Server response: {resp}")
    print()

    # Decodifica comando
    stato_comunicazione = {}
    decode_cmd1(resp, stato_comunicazione)

    # Cache con config di default
    cache = {
        'config': {'width': 630, 'height': 320, 'TOH': 10, 'TOV': 10},
        'stato_comunicazione': stato_comunicazione
    }

    # Punto di test
    punto_test = (315 + 15, 160)  # +15px orizzontale dal centro

    # Verifica is_punto_ok
    result = is_punto_ok(punto_test, cache)

    print(f"  Config default: TOH=10, TOV=10")
    print(f"  Stato comunicazione: {stato_comunicazione}")
    print()
    print(f"  Punto test: {punto_test} (offset +15px dal centro)")
    print(f"  TOH usato: {int(stato_comunicazione.get('TOH', 10))}")
    print(f"  TOV usato: {int(stato_comunicazione.get('TOV', 10))}")
    print(f"  Risultato: {result['status']}")

    # Spiega
    toh_used = int(stato_comunicazione.get('TOH', cache['config']['TOH']))
    if 15 <= toh_used:
        expected = "ok (dentro)"
    elif 15 <= 2*toh_used:
        expected = "warning (poco fuori)"
    else:
        expected = "error (molto fuori)"

    print(f"  Atteso: {expected}")
    print(f"  ✓ CORRETTO" if expected.split()[0] == result['status'] else "  ✗ ERRORE")
    print()
    print("-"*70)
    print()

print("="*70)
print("CONCLUSIONI:")
print("="*70)
print()
print("✅ TOH e TOV possono essere inviati dal server nel formato:")
print("   'TOH <valore>; TOV <valore>;'")
print()
print("✅ Priorità:")
print("   1. Valore da comunicazione (se presente)")
print("   2. Valore da config.json (fallback)")
print()
print("✅ Esempio comando completo:")
print("   'croce 1; run 1; tipo_faro anabbagliante; TOH 30; TOV 20; inclinazione 5;'")
print()
print("✅ I valori da comunicazione permettono aggiustamenti real-time")
print("   senza modificare config.json")
print()
