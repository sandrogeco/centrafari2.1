#!/usr/bin/env python3
"""
Server di test per comunicazione con MW28912.py
"""

import socket
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Configurazione
HOST = 'localhost'
PORT = 8888  # Cambia con la porta del tuo config.json

def create_response():
    """
    Crea una risposta di test nel formato CFG.

    Formato: CFG->{pattern}{croce}xxx{TOV}xxxxxxxxxxxxx{inclinazione}xx{TOH}xx{qin}
    """
    pattern = '0'           # 1 char
    croce = '1'             # 1 char
    tov = '050'             # 3 chars
    inclinazione = '0000'   # 4 chars
    toh = '050'             # 3 chars
    qin = '01.50'           # 5 chars

    # Formato fisso con padding
    response = f"CFG->{pattern}{croce}xxx{tov}xxxxxxxxxxxxx{inclinazione}xx{toh}xx{qin}"
    return response

def main():
    # Crea socket TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(1)

        logging.info(f"🎧 Server in ascolto su {HOST}:{PORT}")
        logging.info("In attesa di connessioni da MW28912.py...")

        while True:
            try:
                conn, addr = server.accept()
                with conn:
                    logging.info(f"✅ Connessione da {addr}")

                    # Ricevi dati
                    data = conn.recv(1024).decode('UTF-8')
                    logging.info(f"📥 RX: {data.strip()}")

                    # Prepara risposta
                    response = create_response()

                    # Invia risposta
                    conn.sendall(response.encode())
                    logging.info(f"📤 TX: {response}")

            except KeyboardInterrupt:
                logging.info("\n👋 Server terminato")
                break
            except Exception as e:
                logging.error(f"❌ Errore: {e}")

if __name__ == "__main__":
    main()
