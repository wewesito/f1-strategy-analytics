"""
Tests de calidad de los datos ya procesados (los que se suben al repositorio).
Comprueban reglas que, si se rompen, indican un error de extracción o de limpieza.
"""

import glob
import os

import pandas as pd
import pytest

import powerbi_export

ARCHIVOS_VUELTAS = sorted(glob.glob(os.path.join('data', 'processed', 'laps_clean_*.parquet')))
STAR = os.path.join('data', 'processed', 'powerbi')

# Pilotos por carrera: entre 18 y 20. Excepción: en 2026 hay 11 equipos (22 coches), así que el máximo es 22.
# (En Australia 2024 hubo 19 y es correcto: no todos los coches toman la salida.)
MIN_PILOTOS = 18
MAX_PILOTOS = {2026: 22}
MAX_PILOTOS_POR_DEFECTO = 20


def leer_estrella(nombre):
    return pd.read_csv(os.path.join(STAR, f'{nombre}.csv'), encoding='utf-8-sig')


@pytest.mark.parametrize('ruta', ARCHIVOS_VUELTAS, ids=os.path.basename)
def test_no_hay_tiempos_negativos(ruta):
    v = pd.read_parquet(ruta)
    assert (v['LapTimeSec'] > 0).all(), 'hay vueltas con tiempo cero o negativo'
    for col in ('Sector1Sec', 'Sector2Sec', 'Sector3Sec'):
        assert (v[col].dropna() > 0).all(), f'{col} tiene tiempos no positivos'


@pytest.mark.parametrize('ruta', ARCHIVOS_VUELTAS, ids=os.path.basename)
def test_no_hay_vueltas_duplicadas(ruta):
    v = pd.read_parquet(ruta)
    duplicadas = v.duplicated(['Year', 'Round', 'Driver', 'LapNumber'])
    assert not duplicadas.any(), f'{duplicadas.sum()} vueltas repetidas (carrera, piloto, vuelta)'


def test_hay_vueltas_procesadas():
    assert ARCHIVOS_VUELTAS, 'no hay ningún laps_clean_*.parquet en data/processed'


def test_vueltas_del_modelo_en_estrella_sin_tiempos_negativos_ni_duplicados():
    v = leer_estrella('fact_vueltas')
    assert (v['TiempoVueltaSeg'] > 0).all()
    assert not v.duplicated(['CarreraId', 'PilotoId', 'Vuelta']).any()


def test_cada_carrera_tiene_entre_18_y_20_pilotos():
    r = leer_estrella('fact_resultados')
    n = r.groupby('CarreraId')['PilotoId'].nunique().reset_index(name='pilotos')
    n['anio'] = n['CarreraId'] // 100
    n['maximo'] = n['anio'].map(MAX_PILOTOS).fillna(MAX_PILOTOS_POR_DEFECTO)
    mal = n[(n['pilotos'] < MIN_PILOTOS) | (n['pilotos'] > n['maximo'])]
    assert mal.empty, f'carreras con un número de pilotos fuera de rango:\n{mal}'


def test_australia_2024_tuvo_19_pilotos():
    r = leer_estrella('fact_resultados')
    assert r[r['CarreraId'] == 202403]['PilotoId'].nunique() == 19


def test_resultados_sin_duplicados_y_con_tres_podios():
    r = leer_estrella('fact_resultados')
    assert not r.duplicated(['CarreraId', 'PilotoId']).any()
    assert (r.groupby('CarreraId')['Podio'].sum() == 3).all(), 'cada carrera debe tener exactamente 3 podios'
    assert (r.groupby('CarreraId')['Victoria'].sum() == 1).all(), 'cada carrera debe tener exactamente 1 ganador'


def test_integridad_referencial_del_modelo_en_estrella():
    """Claves únicas en las dimensiones y sin claves huérfanas en los hechos (misma validación que el exportador)."""
    nombres = ['dim_calendario', 'dim_carrera', 'dim_piloto', 'dim_equipo', 'dim_compuesto', 'fact_resultados',
               'fact_vueltas', 'fact_estrategias', 'fact_degradacion', 'fact_telemetria_tramos', 'fact_predicciones']
    errores = powerbi_export.validar({n: leer_estrella(n) for n in nombres})
    assert not errores, '\n'.join(errores)


def test_probabilidades_de_las_predicciones_son_validas():
    p = leer_estrella('fact_predicciones')
    assert p['ProbaPodio'].between(0, 1).all()
    assert p['ProbaPodioNorm'].between(0, 1).all()
    assert (p.groupby('CarreraId')['PredPodio'].sum() == 3).all(), 'se predicen exactamente 3 podios por carrera'
