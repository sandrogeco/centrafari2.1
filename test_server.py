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
    Crea una risposta di test con formato keyword-based.

    Formato: croce:{val} inclinazione:{val} run:{val}
    """
    croce = '1'           # 1 char
    inclinazione = '00000'  # 5 chars
    run = '1'             # 1 char

    # Formato keyword-based
    response = f"croce:{croce} inclinazione:{inclinazione} run:{run}"
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
