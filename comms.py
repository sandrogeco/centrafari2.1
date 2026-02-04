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


def encode_response(p, cache=None):
    """
    Codifica i dati di risposta in stringa.
    Applica calibrazione e conversione unità di misura.

    Args:
        p: Dict con i parametri da inviare
           (posiz_pattern_x, posiz_pattern_y, lux, roll, yaw, pitch, left, right, up, down)
        cache: Cache con config e stato_comunicazione (per calibrazione e UM)

    Returns:
        Stringa formattata secondo USE_NEW_FORMAT
    """
    # Estrai valori pixel
    pixel_x = p['posiz_pattern_x']
    pixel_y = p['posiz_pattern_y']
    lux = p['lux']

    # Default: output in pixel
    out_x = pixel_x
    out_y = pixel_y
    out_lux = lux

    # Applica calibrazione e conversione UM se cache disponibile
    if cache:
        config = cache.get('config', {})
        stato = cache.get('stato_comunicazione', {})

        # Calibrazione: pixel -> percentuale
        # Riferimento = centro immagine + inclinazione richiesta
        calib_m = config.get('y_calib_m', 1.0)
        width = config.get('width', 640)
        height = config.get('height', 480)
        center_x = width / 2
        center_y = height / 2

        # incl già convertito in pixel nel thread
        incl_pixel = int(stato.get('incl', 0))

        # Calcola percentuale rispetto a centro + inclinazione
        if abs(calib_m) > 0.01:
            perc_x = (pixel_x - center_x) / calib_m
            perc_y = (pixel_y - (center_y + incl_pixel)) / calib_m
        else:
            perc_x = pixel_x
            perc_y = pixel_y

        # UMI: unità misura inclinazione (0=cm, 1=inches, 2=%)
        umi = int(stato.get('UMI', 2))
        if umi == 0:  # cm
            out_x = perc_x * 10
            out_y = perc_y * 10
        elif umi == 1:  # inches
            out_x = perc_x * 10 * 0.3937
            out_y = perc_y * 10 * 0.3937
        else:  # 2 = percentuale
            out_x = perc_x
            out_y = perc_y

        # UMH: unità misura altezza (0=mm, 1=cm, 2=inches) - non usata per ora
        umh = int(stato.get('UMH', 0))
        # TODO: applicare se necessario

        # UMB: unità misura luminosità (0=lux/25m, 1=Kcandles/1m, 2=KLux/1m)
        # Conversione: candela = lux × d² = lux × 625 (a 25m)
        umb = int(stato.get('UMB', 0))
        if umb == 0:  # lux/25m (default, nessuna conversione)
            out_lux = lux
        elif umb == 1:  # Kcandles/1m = lux × 625 / 1000
            out_lux = lux * 0.625
        elif umb == 2:  # KLux/1m = lux × 625 / 1000
            out_lux = lux * 0.625

    if USE_NEW_FORMAT:
        msg = (
            f"x {out_x:.2f}; "
            f"y {out_y:.2f}; "
            f"lux {out_lux:.2f}; "
            f"roll {p['roll']:.2f}; "
            f"yaw {p['yaw']:.2f}; "
            f"pitch {p['pitch']:.2f}; "
            f"left {p['left']}; "
            f"right {p['right']}; "
            f"up {p['up']}; "
            f"down {p['down']};\n"
        )
    else:
        msg = (
            f"XYL {out_x:.2f} {out_y:.2f} "
            f"{out_lux:.2f} {p['roll']:.2f} {p['yaw']:.2f} {p['pitch']:.2f} "
            f"{p['left']} {p['right']} {p['up']} {p['down']}\n"
        )
    # Tronca a 278 byte
    return msg[:278]


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
    Thread di comunicazione sincrona request-response.

    Ciclo:
    1. TX: manda dati punto
    2. RX: aspetta risposta (con timeout)
    3. Rispetta tempo minimo di ciclo
    """
    import time

    conn = None
    last_data = None

    while True:
        cycle_start = time.monotonic()

        # Parametri da config
        config = cache['config']
        cycle_min_ms = config.get('comm_cycle_min_ms', 100)
        timeout_ms = config.get('comm_timeout_ms', 500)

        # === CONNESSIONE ===
        if conn is None:
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((config.get('ip', "localhost"), port))
                logging.info(f"Connesso a {config.get('ip')}:{port}")

                # Manda start_cfg alla connessione
             #   conn.sendall(b"start_cfg ")

            except Exception as e:
                logging.error(f"Connessione fallita: {e}")
                conn = None
                time.sleep(1)
                continue

        # === TX: INVIO DATI ===
        try:
            # Svuota coda e prendi ultimo valore
            while True:
                try:
                    last_data = cache['queue'].get_nowait()
                except:
                    break

            # Manda ultimo dato (o idle se nessun dato)
            if last_data:
                msg = encode_response(last_data, cache)
            else:
                msg = "idle "

            conn.sendall(msg.encode())
            logging.debug(f"[TX] {msg}")

        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logging.error(f"Errore invio: {e}")
            conn.close()
            conn = None
            continue

        # === RX: ATTESA RISPOSTA (bloccante con timeout) ===
        try:
            conn.setblocking(False)
            timeout_sec = timeout_ms / 1000.0
            ready, _, _ = select.select([conn], [], [], timeout_sec)

            if ready:
                data = conn.recv(1024).decode("UTF-8")
                if data:
                    logging.debug(f"[RX] {data}")
                    decode_cmd1(data, cache['stato_comunicazione'])
                    # Converti incl da % a pixel
                    if 'incl' in cache['stato_comunicazione']:
                        incl_percent = float(cache['stato_comunicazione']['incl'])
                        calib_m = cache['config'].get('y_calib_m', 1.0)
                        cache['stato_comunicazione']['incl'] = int(incl_percent * calib_m)
                else:
                    logging.warning("Connessione chiusa dal server")
                    conn.close()
                    conn = None
                    continue
            else:
                logging.warning(f"[RX] Timeout ({timeout_ms}ms) - nessuna risposta")

        except (BlockingIOError, socket.error):
            pass
        except Exception as e:
            logging.error(f"Errore ricezione: {e}")
            conn.close()
            conn = None
            continue

        conn.close()
        conn = None

        # === RISPETTA TEMPO MINIMO CICLO ===
        cycle_elapsed_ms = (time.monotonic() - cycle_start) * 1000
        if cycle_elapsed_ms < cycle_min_ms:
            sleep_time = (cycle_min_ms - cycle_elapsed_ms) / 1000.0
            time.sleep(sleep_time)
