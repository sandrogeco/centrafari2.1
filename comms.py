"""
Modulo comunicazione MW28912.
Gestisce connessione persistente con invio continuo dati e ricezione asincrona.
"""

import socket
import select
import logging


# =============================================================================
# FORMATO MESSAGGI
# Se True usa nuovo formato: "x 123; y 456; lux 0.50; ..."
# Se False usa vecchio formato: "XYL 123 456 0.50 ..."
# =============================================================================
USE_NEW_FORMAT = True


def encode_response(p):
    """
    Codifica i dati di risposta in stringa.

    Args:
        p: Dict con i parametri da inviare
           (posiz_pattern_x, posiz_pattern_y, lux, roll, yaw, pitch, left, right, up, down)

    Returns:
        Stringa formattata secondo USE_NEW_FORMAT
    """
    if USE_NEW_FORMAT:
        # Nuovo formato: parametro valore; parametro2 valore2; ...
        msg = (
            f"x {int(p['posiz_pattern_x'])}; "
            f"y {int(p['posiz_pattern_y'])}; "
            f"lux {p['lux']:.2f}; "
            f"roll {p['roll']:.2f}; "
            f"yaw {p['yaw']:.2f}; "
            f"pitch {p['pitch']:.2f}; "
            f"left {p['left']}; "
            f"right {p['right']}; "
            f"up {p['up']}; "
            f"down {p['down']};"
        )
    else:
        # Vecchio formato: XYL x y lux roll yaw pitch left right up down
        msg = (
            f"XYL {int(p['posiz_pattern_x'])} {int(p['posiz_pattern_y'])} "
            f"{p['lux']:.2f} {p['roll']:.2f} {p['yaw']:.2f} {p['pitch']:.2f} "
            f"{p['left']} {p['right']} {p['up']} {p['down']} "
        )
    return msg


def decode_cmd(resp):
    """Decodifica vecchio formato CFG->..."""
    stato_comunicazione = {}
    if resp.startswith("CFG->"):
        stato_comunicazione['pattern'] = int(resp[5])
        stato_comunicazione['croce'] = int(resp[6])
        stato_comunicazione['TOV'] = int(resp[10:13])
        stato_comunicazione['incl'] = int(resp[27:31])
        stato_comunicazione['TOH'] = int(resp[34:37])
        stato_comunicazione['qin'] = float(resp[40:45])
    return stato_comunicazione


def decode_cmd1(resp, commands):
    """
    Decodifica comandi con formato: parametro valore; parametro2 valore2;
    Esempio: croce 1; run 0; tipo_faro anabbagliante; incl 00000;
    """
    parts = resp.split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        tokens = part.split(' ', 1)
        if len(tokens) == 2:
            parametro = tokens[0].strip()
            valore = tokens[1].strip()
            commands[parametro] = valore


def thread_comunicazione(port, cache):
    """
    Thread di comunicazione con connessione persistente.

    - Mantiene connessione aperta
    - Manda dati punto in continuo (dalla coda)
    - Riceve e decodifica comandi quando arrivano (non bloccante)
    """
    conn = None
    last_data = None  # Ultimo dato valido per reinvio

    while True:
        # === CONNESSIONE ===
        # Se non connesso, prova a connettersi
        if conn is None:
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((cache['config'].get('ip', "localhost"), port))
                conn.setblocking(False)  # Non-bloccante dopo connessione
                logging.info(f"Connesso a {cache['config'].get('ip')}:{port}")

                # Manda start_cfg alla connessione
                conn.sendall(b"start_cfg ")

            except Exception as e:
                logging.error(f"Connessione fallita: {e}")
                conn = None
                import time
                time.sleep(1)  # Attendi prima di riprovare
                continue

        # === INVIO DATI (non bloccante) ===
        try:
            # Svuota coda e prendi ultimo valore
            while True:
                try:
                    last_data = cache['queue'].get_nowait()
                except:
                    break

            # Manda ultimo dato (o idle se nessun dato)
            if last_data:
                msg = encode_response(last_data)
            else:
                msg = "idle "

            conn.sendall(msg.encode())
            logging.debug(f"[TX] {msg}")

        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logging.error(f"Errore invio: {e}")
            conn.close()
            conn = None
            continue

        # === RICEZIONE DATI (non bloccante con select) ===
        try:
            # Controlla se ci sono dati da leggere (timeout 10ms)
            ready, _, _ = select.select([conn], [], [], 0.01)

            if ready:
                data = conn.recv(1024).decode("UTF-8")
                if data:
                    logging.debug(f"[RX] {data}")
                    decode_cmd1(data, cache['stato_comunicazione'])
                else:
                    # Connessione chiusa dal server
                    logging.warning("Connessione chiusa dal server")
                    conn.close()
                    conn = None
                    continue

        except (BlockingIOError, socket.error):
            # Nessun dato disponibile, continua
            pass
        except Exception as e:
            logging.error(f"Errore ricezione: {e}")
            conn.close()
            conn = None
            continue
