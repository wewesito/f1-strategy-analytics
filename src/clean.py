"""
clean.py
Funciones para limpiar las vueltas descargadas con extract.py.

Uso (desde la raíz del proyecto):
    python src/clean.py
"""

import os

import pandas as pd

INPUT_PATH = os.path.join('data', 'raw', 'laps_2024.parquet')
OUTPUT_DIR = os.path.join('data', 'processed')


def convertir_tiempos(df):
    """Añade columnas en segundos a partir de los tiempos (timedelta)."""
    df = df.copy()
    df['LapTimeSec'] = df['LapTime'].dt.total_seconds()
    for s in (1, 2, 3):
        df[f'Sector{s}Sec'] = df[f'Sector{s}Time'].dt.total_seconds()
    return df

def anadir_meteorologia(vueltas, meteo):
    """
    Asigna a cada vuelta la última medición meteorológica anterior a su inicio.
    Usa merge_asof: une por el valor más cercano hacia atrás, dentro de cada carrera.
    """
    meteo = meteo[['Round', 'Time', 'AirTemp', 'TrackTemp', 'Humidity', 'Rainfall']]
    meteo = meteo.rename(columns={'Time': 'MeteoTime'}).sort_values('MeteoTime')

    # merge_asof no admite vacíos en la columna de unión
    vueltas = vueltas.dropna(subset=['LapStartTime']).sort_values('LapStartTime')

    res = pd.merge_asof(
        vueltas, meteo,
        left_on='LapStartTime', right_on='MeteoTime',
        by='Round',              # solo busca dentro de la misma carrera
        direction='backward',    # la medición más reciente ANTES del inicio de la vuelta
    )
    res['Lluvia'] = res['Rainfall'].eq(True)
    return res.drop(columns=['MeteoTime']).sort_values(['Round', 'Driver', 'LapNumber'])

def limpiar_vueltas(df, verbose=True):
    """
    Aplica los filtros de limpieza en orden e informa de cuántas
    vueltas elimina cada paso.
    """
    df = convertir_tiempos(df)
    inicial = len(df)

    pasos = [
        ('Sin tiempo registrado', lambda d: d['LapTimeSec'].notna()),
        ('Primera vuelta', lambda d: d['LapNumber'] > 1),
        ('Entrada/salida de boxes', lambda d: d['PitInTime'].isna() & d['PitOutTime'].isna()),
        ('Pista no verde (SC, VSC, banderas)', lambda d: d['TrackStatus'] == '1'),
        ('Vuelta anulada', lambda d: ~d['Deleted'].eq(True)),
        ('Poco fiable (IsAccurate)', lambda d: d['IsAccurate'].eq(True)),
        ('> 107 % de la mediana (carrera y compuesto)',
         lambda d: d['LapTimeSec'] <= 1.07 * d.groupby(['Round', 'Compound'])['LapTimeSec'].transform('median')),
    ]

    for nombre, condicion in pasos:
        antes = len(df)
        df = df[condicion(df)]
        if verbose:
            print(f'{nombre:<42} -{antes - len(df):>6} vueltas')

    if verbose:
        print(f'\nTotal: {inicial} -> {len(df)} vueltas '
              f'({len(df) / inicial:.1%} conservadas)')

    return df.reset_index(drop=True)


if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    vueltas = pd.read_parquet(INPUT_PATH)
    meteo = pd.read_parquet(os.path.join('data', 'raw', 'weather_2024.parquet'))

    vueltas = anadir_meteorologia(vueltas, meteo)
    limpias = limpiar_vueltas(vueltas)

    print(f"Vueltas limpias con lluvia: {limpias['Lluvia'].sum()}")
    limpias.to_parquet(os.path.join(OUTPUT_DIR, 'laps_clean_2024.parquet'))
    print('Guardado en data/processed/laps_clean_2024.parquet')