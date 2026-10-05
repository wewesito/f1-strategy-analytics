"""
load.py
Carga las vueltas limpias y los resultados en una base de datos DuckDB.

Uso (desde la raíz del proyecto):
    python src/load.py
"""

import os

import duckdb
import pandas as pd

DB_PATH = os.path.join('data', 'f1.duckdb')


def cargar_en_duckdb():
    laps_df = pd.read_parquet(os.path.join('data', 'processed', 'laps_clean_2024.parquet'))
    results_df = pd.read_parquet(os.path.join('data', 'raw', 'results_2024.parquet'))

    con = duckdb.connect(DB_PATH)

    # register: DuckDB puede consultar un DataFrame de pandas como si fuera una tabla
    con.register('laps_df', laps_df)
    con.register('results_df', results_df)

    # CREATE OR REPLACE: si la tabla ya existe, la sustituye (podemos re-ejecutar sin errores)
    con.execute('CREATE OR REPLACE TABLE laps AS SELECT * FROM laps_df')
    con.execute('CREATE OR REPLACE TABLE results AS SELECT * FROM results_df')

    for tabla in ('laps', 'results'):
        n = con.execute(f'SELECT COUNT(*) FROM {tabla}').fetchone()[0]
        print(f'Tabla {tabla}: {n} filas')

    con.close()
    print(f'Base de datos guardada en {DB_PATH}')


if __name__ == '__main__':
    cargar_en_duckdb()