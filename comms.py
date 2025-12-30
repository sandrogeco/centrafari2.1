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

def decode_cmd1(resp,commands):
    def find_cmd(cmd,length):
        start=resp.find(cmd)
        end=start+len(cmd)
        if start>0:
          commands['cmd']=resp[end+1:end+length]

    find_cmd('croce',1)
    find_cmd('inclinazione',5)
    find_cmd('run',1)

def thread_comunicazione(port, cache):
    first_run = True

    while True:
        if first_run:
            msg = "start_cfg "
            first_run = False
        else:
            try:
                p = cache['queue'].get(timeout=0.3)
                msg = f"XYL {int(p['posiz_pattern_x'])} {int(p['posiz_pattern_y'])} {p['lux']:.2f} {p['roll']:.2f} {p['yaw']:.2f} {p['pitch']:.2f} "
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

