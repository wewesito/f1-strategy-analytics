"""
load.py
Carga en DuckDB las vueltas limpias y el resto de tablas de la temporada.

Uso (desde la raíz del proyecto):
    python src/load.py
"""

import os

import duckdb
import pandas as pd

YEAR = 2024
DB_PATH = os.path.join('data', 'f1.duckdb')

# tabla en DuckDB -> archivo Parquet de origen
TABLAS = {
    'laps': os.path.join('data', 'processed', f'laps_clean_{YEAR}.parquet'),
    'results': os.path.join('data', 'raw', f'results_{YEAR}.parquet'),
    'weather': os.path.join('data', 'raw', f'weather_{YEAR}.parquet'),
    'track_status': os.path.join('data', 'raw', f'track_status_{YEAR}.parquet'),
    'race_control': os.path.join('data', 'raw', f'race_control_{YEAR}.parquet'),
    'pit_stops': os.path.join('data', 'raw', f'pit_stops_{YEAR}.parquet'),
}


def cargar_en_duckdb():
    con = duckdb.connect(DB_PATH)

    for tabla, ruta in TABLAS.items():
        if not os.path.exists(ruta):
            print(f'AVISO: no existe {ruta}, se omite la tabla {tabla}')
            continue
        df = pd.read_parquet(ruta)
        con.register('df_temporal', df)
        con.execute(f'CREATE OR REPLACE TABLE {tabla} AS SELECT * FROM df_temporal')
        con.unregister('df_temporal')
        print(f'Tabla {tabla:<13} {len(df):>7} filas')

    con.close()
    print(f'\nBase de datos guardada en {DB_PATH}')


if __name__ == '__main__':
    cargar_en_duckdb()