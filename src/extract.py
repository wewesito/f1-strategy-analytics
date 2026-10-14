"""
extract.py
Descarga una temporada de F1: vueltas, resultados, meteorología, estado de pista,
mensajes de dirección de carrera y paradas en boxes. Lo guarda en data/raw/.

Las fuentes adicionales se inspiran en f1-race-replay (Tom Shaw, licencia MIT):
https://github.com/IAmTomShaw/f1-race-replay

Uso (desde la raíz del proyecto):
    python src/extract.py                         # temporada 2024 completa (como siempre)
    python src/extract.py --year 2026 --solo-nuevas   # solo las carreras disputadas que faltan
"""

import argparse
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


TABLAS = ('laps', 'results', 'weather', 'track_status', 'race_control', 'pit_stops')


def ruta_raw(nombre, year):
    return os.path.join(OUTPUT_DIR, f'{nombre}_{year}.parquet')


def rondas_descargadas(year):
    """Rondas que ya están en data/raw/ (se miran en la tabla de vueltas). Vacío si no hay nada."""
    ruta = ruta_raw('laps', year)
    if not os.path.exists(ruta):
        return set()
    return set(pd.read_parquet(ruta, columns=['Round'])['Round'].unique())


def rondas_pendientes(calendario, descargadas, ahora=None):
    """
    Rondas disputadas (la carrera terminó hace más de 3 horas) que todavía no se han descargado.
    La fecha de la carrera es la de la sesión 5 del calendario de FastF1 (con zona horaria).
    """
    ahora = ahora or pd.Timestamp.now(tz='UTC')
    fin_carrera = pd.to_datetime(calendario['Session5DateUtc'], utc=True) + pd.Timedelta(3, unit='h')
    disputada = fin_carrera < ahora
    ya = calendario['RoundNumber'].isin(descargadas)
    return calendario[disputada & ~ya]


def descargar_carrera(year, ronda):
    """Descarga una carrera y devuelve un dict {tabla: DataFrame} con las 6 tablas (Year, Round y Event añadidos)."""
    session = fastf1.get_session(year, ronda, 'R')
    # También meteorología y mensajes (como f1-race-replay)
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
        df['Event'] = session.event['EventName']
        tablas[nombre] = df
    return tablas


def descargar_temporada(year=YEAR, solo_nuevas=False):
    """
    Descarga una temporada y la guarda en data/raw/.
    - solo_nuevas=False (por defecto, como siempre): intenta todas las rondas del calendario y reescribe los archivos.
    - solo_nuevas=True: descarga únicamente las carreras ya disputadas que aún no están en data/raw/ y las
      AÑADE a lo que ya hay. Es lo que usa el pipeline semanal.
    Devuelve la lista de rondas descargadas.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)
    fastf1.set_log_level('WARNING')

    calendario = fastf1.get_event_schedule(year, include_testing=False)
    previas = rondas_descargadas(year) if solo_nuevas else set()
    pendientes = rondas_pendientes(calendario, previas) if solo_nuevas else calendario
    total = len(calendario)

    if solo_nuevas:
        print(f'{year}: {len(previas)} carreras ya descargadas, {len(pendientes)} nuevas por descargar')

    datos = {nombre: [] for nombre in TABLAS}
    nuevas = []

    for _, evento in pendientes.iterrows():
        ronda = evento['RoundNumber']
        print(f'[{ronda}/{total}] {evento["EventName"]}...', end=' ', flush=True)
        try:
            tablas = descargar_carrera(year, ronda)
            for nombre, df in tablas.items():
                datos[nombre].append(df)
            nuevas.append(int(ronda))
            print(f'OK ({len(tablas["laps"])} vueltas, {len(tablas["pit_stops"])} paradas)')
        except Exception as error:
            print(f'ERROR: {error}')

    print()
    for nombre, lista in datos.items():
        if not lista:
            continue
        df = pd.concat(lista, ignore_index=True)
        ruta = ruta_raw(nombre, year)
        if solo_nuevas and os.path.exists(ruta):
            df = pd.concat([pd.read_parquet(ruta), df], ignore_index=True)   # añade a lo existente
        df.to_parquet(ruta)
        print(f'Guardado {ruta}: {len(df)} filas')
    return nuevas


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Descarga una temporada de F1 con FastF1 a data/raw/.')
    parser.add_argument('--year', type=int, default=YEAR, help=f'temporada (por defecto {YEAR})')
    parser.add_argument('--solo-nuevas', action='store_true', help='descarga solo las carreras disputadas que faltan')
    args = parser.parse_args()
    descargar_temporada(args.year, solo_nuevas=args.solo_nuevas)
