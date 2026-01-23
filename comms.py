"""
Modulo comunicazione MW28912.
Due thread indipendenti:
    - RX (porta 25800): riceve comandi
    - TX (porta 28501): trasmette dati punto
"""

import socket
import logging
import time


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

    Returns:
        Stringa formattata secondo USE_NEW_FORMAT
    """
    if USE_NEW_FORMAT:
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


# =============================================================================
# THREAD RX - Riceve comandi sulla porta 25800
# =============================================================================
def thread_rx(port, cache):
    """
    Thread di ricezione comandi.
    Ascolta sulla porta specificata e decodifica comandi in arrivo.

    Args:
        port: Porta di ascolto (default 25800)
        cache: Cache condivisa con stato_comunicazione
    """
    server = None

    while True:
        # Crea server socket se non esiste
        if server is None:
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(('0.0.0.0', port))
                server.listen(1)
                logging.info(f"[RX] In ascolto su porta {port}")
            except Exception as e:
                logging.error(f"[RX] Errore bind porta {port}: {e}")
                server = None
                time.sleep(1)
                continue

        # Accetta connessioni
        try:
            server.settimeout(1.0)  # Timeout per non bloccare indefinitamente
            conn, addr = server.accept()
            logging.info(f"[RX] Connessione da {addr}")

            conn.settimeout(0.1)

            while True:
                try:
                    data = conn.recv(1024).decode("UTF-8")
                    if not data:
                        break  # Connessione chiusa

                    logging.debug(f"[RX] {data}")
                    decode_cmd1(data, cache['stato_comunicazione'])

                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"[RX] Errore ricezione: {e}")
                    break

            conn.close()

        except socket.timeout:
            continue
        except Exception as e:
            logging.error(f"[RX] Errore accept: {e}")
            time.sleep(0.1)


# =============================================================================
# THREAD TX - Trasmette dati sulla porta 28501
# =============================================================================
def thread_tx(port, cache):
    """
    Thread di trasmissione dati.
    Connette alla porta specificata e invia dati punto in continuo.

    Args:
        port: Porta di destinazione (default 28501)
        cache: Cache con queue dati da inviare
    """
    conn = None
    last_data = None

    while True:
        # Connetti se non connesso
        if conn is None:
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((cache['config'].get('ip', 'localhost'), port))
                logging.info(f"[TX] Connesso a {cache['config'].get('ip')}:{port}")
            except Exception as e:
                logging.error(f"[TX] Connessione fallita: {e}")
                conn = None
                time.sleep(1)
                continue

        # Prendi ultimo dato dalla coda (non bloccante)
        while True:
            try:
                last_data = cache['queue'].get_nowait()
            except:
                break

        # Invia dato
        try:
            if last_data:
                msg = encode_response(last_data)
            else:
                msg = "idle "

            conn.sendall(msg.encode())
            logging.debug(f"[TX] {msg}")

        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logging.error(f"[TX] Errore invio: {e}")
            conn.close()
            conn = None
            continue

        # Piccola pausa per non saturare
        time.sleep(0.01)


# =============================================================================
# FUNZIONE LEGACY (per compatibilita')
# =============================================================================
def thread_comunicazione(port, cache):
    """
    Funzione legacy - ora usa thread separati.
    Mantiene compatibilita' chiamando thread_tx.
    """
    thread_tx(port, cache)
