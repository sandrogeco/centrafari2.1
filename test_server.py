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
    Crea una risposta di test con nuovo formato a lunghezza variabile.

    Formato: parametro valore; parametro2 valore2;
    Esempio: croce 1; run 0; tipo_faro anabbagliante;
    """
    croce = '1'
    incl = '00000'
    run = '1'
    tipo_faro = 'anabbagliante'  # anabbagliante, abbagliante, fendinebbia

    # Nuovo formato con lunghezza automatica
    response = f"croce {croce}; incl {incl}; run {run}; tipo_faro {tipo_faro};"
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
