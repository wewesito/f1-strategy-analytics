"""
extract_history.py
Descarga el histórico de resultados y clasificaciones 2018-2026 desde la API de
Jolpica (sucesora de Ergast) y lo guarda en data/raw/. Solo se incluyen las
carreras ya disputadas (fecha anterior a hoy), porque la temporada en curso
tiene carreras futuras en el calendario.

Se usa Jolpica y no FastF1 porque devuelve toda una temporada en unas pocas
peticiones y no necesita descargar telemetría.

Uso (desde la raíz del proyecto):
    python src/extract_history.py
"""

import os
import time
from datetime import date

import pandas as pd
import requests

URL_BASE = 'https://api.jolpi.ca/ergast/f1'
PRIMER_ANIO = 2018
OUTPUT_DIR = os.path.join('data', 'raw')
TAM_PAGINA = 100  # máximo de filas por petición que admite la API
PAUSA = 0.5  # segundos entre peticiones (la API limita el ritmo)


def pedir(url, params):
    """GET con reintentos: si la API responde 429 (demasiadas peticiones) espera y reintenta."""
    for intento in range(6):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(5 * (intento + 1))
            continue
        r.raise_for_status()
        time.sleep(PAUSA)
        return r.json()['MRData']
    raise RuntimeError(f'La API sigue limitando las peticiones: {url}')


def descargar_carreras(year, endpoint, clave):
    """
    Descarga todas las carreras de una temporada paginando.
    endpoint: 'results' o 'qualifying'; clave: lista dentro de cada carrera
    ('Results' o 'QualifyingResults'). Devuelve una lista de (carrera, filas).
    """
    carreras, offset = {}, 0
    while True:
        datos = pedir(f'{URL_BASE}/{year}/{endpoint}.json', {'limit': TAM_PAGINA, 'offset': offset})
        for carrera in datos['RaceTable']['Races']:
            # una carrera puede quedar partida entre dos páginas: se agrupan por ronda
            entrada = carreras.setdefault(carrera['round'], (carrera, []))
            entrada[1].extend(carrera[clave])
        offset += TAM_PAGINA
        if offset >= int(datos['total']):
            return list(carreras.values())


def base_fila(carrera, fila):
    """Campos comunes a resultados y clasificación."""
    return {
        'Year': int(carrera['season']),
        'Round': int(carrera['round']),
        'Event': carrera['raceName'],
        'Date': carrera['date'],
        'CircuitId': carrera['Circuit']['circuitId'],
        'DriverId': fila['Driver']['driverId'],
        'Abbreviation': fila['Driver'].get('code'),
        'DriverName': f"{fila['Driver']['givenName']} {fila['Driver']['familyName']}",
        'Nationality': fila['Driver'].get('nationality'),
        'TeamId': fila['Constructor']['constructorId'],
        'TeamName': fila['Constructor']['name'],
    }


def tabla_resultados(carreras):
    filas = []
    for carrera, resultados in carreras:
        for r in resultados:
            f = base_fila(carrera, r)
            f.update(
                {
                    'Position': int(r['position']),  # posición final (incluye abandonos al final)
                    'PositionText': r['positionText'],  # 'R' = retirado, 'D' = descalificado...
                    'Grid': int(r['grid']),  # 0 = salida desde el pit lane
                    'Points': float(r['points']),
                    'Laps': int(r['laps']),
                    'Status': r['status'],
                }
            )
            filas.append(f)
    return pd.DataFrame(filas)


def tabla_quali(carreras):
    filas = []
    for carrera, resultados in carreras:
        for r in resultados:
            f = base_fila(carrera, r)
            f.update({'QualiPosition': int(r['position']), 'Q1': r.get('Q1'), 'Q2': r.get('Q2'), 'Q3': r.get('Q3')})
            filas.append(f)
    return pd.DataFrame(filas)


def _descargar_rango(primer_anio, ultimo_anio):
    """Descarga resultados y clasificaciones de un rango de años. Devuelve (resultados, clasificaciones)."""
    hoy = date.today()
    resultados, quali = [], []
    for year in range(primer_anio, ultimo_anio + 1):
        for endpoint, clave, destino in (
            ('results', 'Results', resultados),
            ('qualifying', 'QualifyingResults', quali),
        ):
            carreras = descargar_carreras(year, endpoint, clave)
            # solo carreras ya disputadas (evita filas de carreras futuras)
            carreras = [c for c in carreras if date.fromisoformat(c[0]['date']) < hoy]
            destino.extend(carreras)
            print(f'{year} {endpoint:<11} {len(carreras)} carreras')
    return tabla_resultados(resultados), tabla_quali(quali)


def descargar_historico(primer_anio=PRIMER_ANIO, ultimo_anio=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ultimo_anio = ultimo_anio or date.today().year
    resultados, quali = _descargar_rango(primer_anio, ultimo_anio)
    for nombre, df in (('history_results', resultados), ('history_quali', quali)):
        ruta = os.path.join(OUTPUT_DIR, f'{nombre}.parquet')
        df.to_parquet(ruta)
        print(f'Guardado {ruta}: {len(df)} filas')


def actualizar_historico(year):
    """
    Actualización incremental: si el histórico ya existe, solo se vuelve a descargar `year` y se sustituyen
    sus filas (así aparecen las carreras nuevas). Si no existe, se descarga todo desde 2018.
    """
    rutas = {n: os.path.join(OUTPUT_DIR, f'{n}.parquet') for n in ('history_results', 'history_quali')}
    if not all(os.path.exists(r) for r in rutas.values()):
        print('No hay histórico previo: se descarga completo.')
        return descargar_historico(PRIMER_ANIO, year)

    nuevos = dict(zip(rutas, _descargar_rango(year, year)))
    for nombre, ruta in rutas.items():
        previo = pd.read_parquet(ruta)
        df = pd.concat([previo[previo['Year'] != year], nuevos[nombre]], ignore_index=True)
        df = df.sort_values(['Year', 'Round']).reset_index(drop=True)
        df.to_parquet(ruta)
        print(f'Actualizado {ruta}: {len(df)} filas ({len(nuevos[nombre])} de {year})')


if __name__ == '__main__':
    descargar_historico()
