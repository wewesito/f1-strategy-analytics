"""
stream_client.py
Se conecta al flujo de telemetría de f1-race-replay (Tom Shaw, licencia MIT)
y guarda los datos de cada piloto en un CSV.

Uso:
  1) En f1-race-replay:  python main.py --telemetry   (y elegir una carrera)
  2) En este proyecto:   python src/stream_client.py
  Pulsa Ctrl + C para parar la grabación.
"""

import csv
import json
import os
import socket
import time

HOST, PORT = 'localhost', 9999
SALIDA = os.path.join('data', 'raw', 'stream_replay.csv')
CADA_N = 25   # guardamos 1 de cada 25 fotogramas (≈ 1 por segundo de carrera)

CAMPOS = ['frame_index', 't', 'lap', 'track_status', 'driver', 'position',
          'speed', 'gear', 'drs', 'tyre', 'x', 'y']


def conectar():
    """Intenta conectarse cada 2 segundos hasta que la repetición esté emitiendo."""
    while True:
        try:
            s = socket.create_connection((HOST, PORT))
            print('Conectado a f1-race-replay')
            return s
        except ConnectionRefusedError:
            print('Esperando a f1-race-replay... (¿lo has lanzado con --telemetry?)')
            time.sleep(2)


def main():
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    sock = conectar()
    filas, ultimo = 0, None

    with sock, sock.makefile('r', encoding='utf-8') as flujo, \
            open(SALIDA, 'w', newline='') as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS)
        escritor.writeheader()
        try:
            for linea in flujo:                       # un mensaje JSON por línea
                if not linea.strip():
                    continue
                msg = json.loads(linea)
                idx = msg.get('frame_index')
                # Saltamos fotogramas repetidos (en pausa) y nos quedamos con 1 de cada CADA_N
                if idx is None or idx == ultimo or idx % CADA_N:
                    continue
                ultimo = idx

                frame = msg.get('frame') or {}
                for piloto, d in (frame.get('drivers') or {}).items():
                    escritor.writerow({
                        'frame_index': idx, 't': frame.get('t'), 'lap': frame.get('lap'),
                        'track_status': msg.get('track_status'), 'driver': piloto,
                        'position': d.get('position'), 'speed': d.get('speed'),
                        'gear': d.get('gear'), 'drs': d.get('drs'), 'tyre': d.get('tyre'),
                        'x': d.get('x'), 'y': d.get('y'),
                    })
                    filas += 1
                print(f'\rVuelta {frame.get("lap")} · {filas} filas guardadas', end='')
        except KeyboardInterrupt:
            pass

    print(f'\nGuardadas {filas} filas en {SALIDA}')


if __name__ == '__main__':
    main()