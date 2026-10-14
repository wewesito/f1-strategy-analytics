"""
load.py
Carga en DuckDB las vueltas limpias y el resto de tablas de la temporada.

Uso (desde la raíz del proyecto):
    python src/load.py              # temporada 2024 (como siempre)
    python src/load.py --year 2026
"""

import argparse
import os

import duckdb
import pandas as pd

YEAR = 2024
DB_PATH = os.path.join('data', 'f1.duckdb')


def tablas_del_anio(year):
    """tabla en DuckDB -> archivo Parquet de origen, para un año."""
    return {
        'laps': os.path.join('data', 'processed', f'laps_clean_{year}.parquet'),
        'results': os.path.join('data', 'raw', f'results_{year}.parquet'),
        'weather': os.path.join('data', 'raw', f'weather_{year}.parquet'),
        'track_status': os.path.join('data', 'raw', f'track_status_{year}.parquet'),
        'race_control': os.path.join('data', 'raw', f'race_control_{year}.parquet'),
        'pit_stops': os.path.join('data', 'raw', f'pit_stops_{year}.parquet'),
    }


TABLAS = tablas_del_anio(YEAR)    # se mantiene por compatibilidad


def cargar_en_duckdb(year=YEAR):
    """Crea (o reemplaza) las tablas de DuckDB con los datos de un año."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = duckdb.connect(DB_PATH)

    for tabla, ruta in tablas_del_anio(year).items():
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
    parser = argparse.ArgumentParser(description='Carga en DuckDB las tablas de una temporada.')
    parser.add_argument('--year', type=int, default=YEAR, help=f'temporada (por defecto {YEAR})')
    cargar_en_duckdb(parser.parse_args().year)
