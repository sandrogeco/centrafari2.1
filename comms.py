import socket
import logging


def decode_cmd(resp):
    stato_comunicazione = {}
    if resp.startswith("CFG->"):
        stato_comunicazione['pattern'] = int(resp[5])
        stato_comunicazione['croce'] = int(resp[6])
        stato_comunicazione['TOV'] = int(resp[10:13])
        stato_comunicazione['inclinazione'] = int(resp[27:31])
        stato_comunicazione['TOH'] = int(resp[34:37])
        stato_comunicazione['qin'] = float(resp[40:45])

    return stato_comunicazione

def decode_cmd1(resp, commands):
    """
    Decodifica comandi con formato: parametro valore; parametro2 valore2;
    Esempio: croce 1; run 0; tipo_faro anabbagliante; inclinazione 00000;
    """
    # Splitta per punto e virgola per ottenere ogni comando
    parts = resp.split(';')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Splitta per spazio: primo elemento è parametro, resto è valore
        tokens = part.split(' ', 1)
        if len(tokens) == 2:
            parametro = tokens[0].strip()
            valore = tokens[1].strip()
            commands[parametro] = valore

def thread_comunicazione(port, cache):
    first_run = True

    while True:
        if first_run:
            msg = "start_cfg "
            first_run = False
        else:
            try:
                p = cache['queue'].get(timeout=0.3)
                msg = f"XYL {int(p['posiz_pattern_x'])} {int(p['posiz_pattern_y'])} {p['lux']:.2f} {p['roll']:.2f} {p['yaw']:.2f} {p['pitch']:.2f} {p['left']} {p['right']} {p['up']} {p['down']} "
            except:
                msg = "idle "
            
        try:
            conn = socket.socket()
            conn.connect((cache['config'].get('ip',"localhost"), port))
            conn.sendall(msg.encode())
            data = conn.recv(1024).decode("UTF-8")
           # cache['stato_comunicazione'].update(decode_cmd1(data))
            decode_cmd1(data,cache['stato_comunicazione'])
            print(cache['stato_comunicazione'])
        except Exception as e:
            logging.error(f"thread_comunicazione: error: {e}")
            continue

        logging.debug(f"[TX] {msg}")
        logging.debug(f"[RX] {data}")

