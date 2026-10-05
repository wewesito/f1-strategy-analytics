"""
extract.py
Descarga las vueltas y resultados de todas las carreras de una temporada de F1
y los guarda en data/raw/ en formato Parquet.

Uso (desde la raíz del proyecto):
    python src/extract.py
"""

import os

import fastf1
import pandas as pd

# --- Configuración ---
YEAR = 2024
CACHE_DIR = 'cache'
OUTPUT_DIR = os.path.join('data', 'raw')


def descargar_temporada(year):
    """Descarga vueltas y resultados de todas las carreras de `year`."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)
    fastf1.set_log_level('WARNING')  # menos mensajes INFO en pantalla

    # Calendario de la temporada, sin los test de pretemporada
    calendario = fastf1.get_event_schedule(year, include_testing=False)
    total = len(calendario)

    todas_vueltas = []
    todos_resultados = []

    for _, evento in calendario.iterrows():
        ronda = evento['RoundNumber']
        nombre = evento['EventName']
        print(f'[{ronda}/{total}] {nombre}...', end=' ', flush=True)

        try:
            session = fastf1.get_session(year, ronda, 'R')
            # Solo cargamos lo necesario: sin telemetría (pesa mucho)
            session.load(laps=True, telemetry=False, weather=False, messages=False)

            vueltas = pd.DataFrame(session.laps)
            resultados = pd.DataFrame(session.results)

            # Añadimos columnas para saber de qué carrera es cada fila
            for df in (vueltas, resultados):
                df['Year'] = year
                df['Round'] = ronda
                df['Event'] = nombre

            todas_vueltas.append(vueltas)
            todos_resultados.append(resultados)
            print(f'OK ({len(vueltas)} vueltas)')

        except Exception as error:
            # Si una carrera falla, la saltamos y seguimos con las demás
            print(f'ERROR: {error}')

    # Unimos todas las carreras en una sola tabla
    vueltas_df = pd.concat(todas_vueltas, ignore_index=True)
    resultados_df = pd.concat(todos_resultados, ignore_index=True)

    vueltas_df.to_parquet(os.path.join(OUTPUT_DIR, f'laps_{year}.parquet'))
    resultados_df.to_parquet(os.path.join(OUTPUT_DIR, f'results_{year}.parquet'))

    print(f'\nGuardado: {len(vueltas_df)} vueltas y {len(resultados_df)} resultados '
          f'de {len(todos_resultados)} carreras.')


if __name__ == '__main__':
    descargar_temporada(YEAR)
    