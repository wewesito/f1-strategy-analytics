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
    limpias = limpiar_vueltas(vueltas)
    limpias.to_parquet(os.path.join(OUTPUT_DIR, 'laps_clean_2024.parquet'))
    print('Guardado en data/processed/laps_clean_2024.parquet')