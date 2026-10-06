"""
extract.py
Descarga una temporada de F1: vueltas, resultados, meteorología, estado de pista,
mensajes de dirección de carrera y paradas en boxes. Lo guarda en data/raw/.

Las fuentes adicionales se inspiran en f1-race-replay (Tom Shaw, licencia MIT):
https://github.com/IAmTomShaw/f1-race-replay

Uso (desde la raíz del proyecto):
    python src/extract.py
"""

import os

import fastf1
import pandas as pd

YEAR = 2024
CACHE_DIR = 'cache'
OUTPUT_DIR = os.path.join('data', 'raw')


def periodos_estado_pista(track_status):
    """Convierte cada cambio de estado de pista en un periodo con inicio, fin y duración."""
    df = pd.DataFrame(track_status).copy()
    df['Status'] = df['Status'].astype(str)
    df['InicioSec'] = df['Time'].dt.total_seconds()
    df['FinSec'] = df['InicioSec'].shift(-1)      # el periodo acaba cuando empieza el siguiente
    df['DuracionSec'] = df['FinSec'] - df['InicioSec']
    return df.drop(columns=['Time'])


def paradas_en_boxes(vueltas):
    """
    Una fila por parada. La entrada a boxes (PitInTime) está en la vuelta de entrada,
    y la salida (PitOutTime) en la vuelta siguiente.
    """
    v = vueltas.sort_values(['Driver', 'LapNumber']).copy()
    v['PitOutSiguiente'] = v.groupby('Driver')['PitOutTime'].shift(-1)
    p = v[v['PitInTime'].notna()].copy()
    p['TiempoPitLaneSec'] = (p['PitOutSiguiente'] - p['PitInTime']).dt.total_seconds()
    p = p.rename(columns={'Compound': 'CompuestoQuitado', 'TyreLife': 'VueltasNeumatico'})
    return p[['Driver', 'Team', 'LapNumber', 'CompuestoQuitado', 'VueltasNeumatico', 'TiempoPitLaneSec']]


def columnas_texto_a_string(df):
    """Convierte columnas de texto mixtas a string para poder guardarlas en Parquet."""
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype('string')
    return df


def descargar_temporada(year):
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)
    fastf1.set_log_level('WARNING')

    calendario = fastf1.get_event_schedule(year, include_testing=False)
    total = len(calendario)

    datos = {nombre: [] for nombre in
             ('laps', 'results', 'weather', 'track_status', 'race_control', 'pit_stops')}

    for _, evento in calendario.iterrows():
        ronda = evento['RoundNumber']
        nombre_gp = evento['EventName']
        print(f'[{ronda}/{total}] {nombre_gp}...', end=' ', flush=True)

        try:
            session = fastf1.get_session(year, ronda, 'R')
            # Ahora también meteorología y mensajes (como f1-race-replay)
            session.load(laps=True, telemetry=False, weather=True, messages=True)

            vueltas = pd.DataFrame(session.laps)

            tablas = {
                'laps': vueltas,
                'results': pd.DataFrame(session.results),
                'weather': pd.DataFrame(session.weather_data),
                'track_status': periodos_estado_pista(session.track_status),
                'race_control': columnas_texto_a_string(pd.DataFrame(session.race_control_messages)),
                'pit_stops': paradas_en_boxes(vueltas),
            }

            for nombre, df in tablas.items():
                df = df.copy()
                df['Year'] = year
                df['Round'] = ronda
                df['Event'] = nombre_gp
                datos[nombre].append(df)

            print(f'OK ({len(vueltas)} vueltas, {len(tablas["pit_stops"])} paradas)')

        except Exception as error:
            print(f'ERROR: {error}')

    print()
    for nombre, lista in datos.items():
        if lista:
            df = pd.concat(lista, ignore_index=True)
            ruta = os.path.join(OUTPUT_DIR, f'{nombre}_{year}.parquet')
            df.to_parquet(ruta)
            print(f'Guardado {ruta}: {len(df)} filas')


if __name__ == '__main__':
    descargar_temporada(YEAR)