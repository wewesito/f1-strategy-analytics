"""
Tests de las variables del modelo: ninguna debe usar información de la propia carrera ni del futuro.
Se usan datos sintéticos pequeños (para poder calcular a mano el resultado esperado) y, si existe, el
histórico real.
"""

import os

import numpy as np
import pandas as pd
import pytest

import features as ft


def datos_sinteticos():
    """
    Dos temporadas (2023 y 2024) con 3 carreras cada una, en los mismos 3 circuitos, y 3 pilotos:
    A y B (equipo T1) y C (equipo T2). Las posiciones son distintas en cada carrera para poder distinguirlas.
    """
    posiciones = {  # (año, ronda) -> posiciones de A, B, C
        (2023, 1): (1, 2, 3),
        (2023, 2): (3, 1, 2),
        (2023, 3): (2, 3, 1),
        (2024, 1): (1, 3, 2),
        (2024, 2): (2, 1, 3),
        (2024, 3): (3, 2, 1),
    }
    puntos = {1: 25, 2: 18, 3: 15}
    filas, quali = [], []
    for (anio, ronda), pos in posiciones.items():
        for piloto, equipo, p in zip('ABC', ('T1', 'T1', 'T2'), pos):
            filas.append(
                {
                    'Year': anio,
                    'Round': ronda,
                    'Event': f'GP{ronda}',
                    'Date': f'{anio}-0{ronda}-01',
                    'CircuitId': f'circuito{ronda}',
                    'DriverId': piloto,
                    'Abbreviation': piloto,
                    'TeamId': equipo,
                    'TeamName': equipo,
                    'Position': p,
                    'PositionText': str(p),
                    'Grid': 0 if (anio, ronda, piloto) == (2024, 2, 'C') else p,  # C sale del pit lane en 2024 R2
                    'Points': puntos[p],
                    'Laps': 50,
                    'Status': 'Finished',
                }
            )
            quali.append(
                {
                    'Year': anio,
                    'Round': ronda,
                    'DriverId': piloto,
                    'QualiPosition': p,
                    'Q1': '1:20.000',
                    'Q2': '1:19.500' if p < 3 else None,
                    'Q3': f'1:19.{p}00' if p < 2 else None,
                }
            )
    return pd.DataFrame(filas), pd.DataFrame(quali)


def fila(df, anio, ronda, piloto):
    return df[(df['Year'] == anio) & (df['Round'] == ronda) & (df['DriverId'] == piloto)].iloc[0]


def test_ninguna_variable_es_el_resultado_de_la_propia_carrera():
    prohibidas = {'Position', 'PositionText', 'Points', 'Podio', 'Status', 'Laps', 'PosicionReal'}
    assert not prohibidas & set(ft.FEATURES)


def test_primera_carrera_no_tiene_historia():
    r, q = datos_sinteticos()
    d = ft.construir_variables(r, q)
    a = fila(d, 2023, 1, 'A')
    assert a['PuntosPilotoAntes'] == 0 and a['PuntosEquipoAntes'] == 0
    assert np.isnan(a['MediaUlt3']) and np.isnan(a['PosCircuitoPrevia'])


def test_puntos_antes_son_los_acumulados_hasta_la_carrera_anterior():
    r, q = datos_sinteticos()
    d = ft.construir_variables(r, q)
    # B en 2023: R1 acabó 2º (18 pts), R2 1º (25 pts). Antes de R3 lleva 43.
    assert fila(d, 2023, 2, 'B')['PuntosPilotoAntes'] == 18
    assert fila(d, 2023, 3, 'B')['PuntosPilotoAntes'] == 43
    # Los puntos se reinician cada temporada
    assert fila(d, 2024, 1, 'B')['PuntosPilotoAntes'] == 0
    # Equipo T1 (A+B) antes de R3 de 2023: R1 = 25+18, R2 = 15+25
    assert fila(d, 2023, 3, 'A')['PuntosEquipoAntes'] == (25 + 18) + (15 + 25)


def test_media_de_las_3_ultimas_carreras_usa_solo_carreras_anteriores():
    r, q = datos_sinteticos()
    d = ft.construir_variables(r, q)
    # A: posiciones 1, 3, 2 en 2023 y 1, 2, 3 en 2024
    assert fila(d, 2023, 2, 'A')['MediaUlt3'] == 1  # solo R1
    assert fila(d, 2023, 3, 'A')['MediaUlt3'] == pytest.approx((1 + 3) / 2)
    assert fila(d, 2024, 1, 'A')['MediaUlt3'] == pytest.approx((1 + 3 + 2) / 3)  # continúa entre temporadas
    assert fila(d, 2024, 3, 'A')['MediaUlt3'] == pytest.approx((2 + 1 + 2) / 3)  # ventana de 3: R3-23, R1-24, R2-24


def test_resultado_en_el_circuito_es_el_de_la_edicion_anterior():
    r, q = datos_sinteticos()
    d = ft.construir_variables(r, q)
    assert np.isnan(fila(d, 2023, 2, 'B')['PosCircuitoPrevia'])
    assert fila(d, 2024, 2, 'B')['PosCircuitoPrevia'] == 1  # B ganó circuito2 en 2023


def test_el_pit_lane_cuenta_como_la_posicion_20():
    r, q = datos_sinteticos()
    d = ft.construir_variables(r, q)
    assert fila(d, 2024, 2, 'C')['Grid'] == 0
    assert fila(d, 2024, 2, 'C')['GridAdj'] == ft.GRID_PIT_LANE == 20


def test_diferencia_con_la_pole_se_calcula_con_la_mejor_vuelta():
    r, q = datos_sinteticos()
    d = ft.construir_variables(r, q)
    pole = fila(d, 2023, 1, 'A')  # Q3 = 1:19.100
    assert pole['DifPolePct'] == pytest.approx(0)
    otro = fila(d, 2023, 1, 'C')  # solo Q1 = 1:20.000 (80 s) frente a 79.1 s
    assert otro['DifPolePct'] == pytest.approx((80.0 - 79.1) / 79.1 * 100)


@pytest.mark.parametrize('texto,esperado', [('1:19.507', 79.507), ('54.309', 54.309), ('1:00.000', 60.0)])
def test_parseo_de_tiempos_de_clasificacion(texto, esperado):
    assert ft.tiempo_a_segundos(texto) == pytest.approx(esperado)


@pytest.mark.parametrize('vacio', [None, '', np.nan])
def test_tiempo_vacio_es_nan(vacio):
    assert np.isnan(ft.tiempo_a_segundos(vacio))


def test_modificar_una_carrera_no_cambia_las_variables_de_esa_carrera_ni_de_las_anteriores():
    """Prueba de invarianza: si cambiara algo, habría información futura (data leakage)."""
    r, q = datos_sinteticos()
    base = ft.construir_variables(r, q)

    r2 = r.copy()
    m = (r2['Year'] == 2023) & (r2['Round'] == 2)
    r2.loc[m, 'Position'] = [1, 2, 3]
    r2.loc[m, 'Points'] = 999
    alterado = ft.construir_variables(r2, q)

    clave = ['Year', 'Round', 'DriverId']
    a = base.set_index(clave)[ft.FEATURES]
    b = alterado.set_index(clave)[ft.FEATURES].loc[a.index]
    cambia = ~((a == b) | (a.isna() & b.isna())).all(axis=1)

    assert cambia.any(), 'el test no detecta ningún cambio: la alteración no tiene efecto'
    primera = min((y, rd) for y, rd, _ in a.index[cambia])
    assert primera > (2023, 2), f'las variables de {primera} cambian al alterar un resultado posterior o propio'


@pytest.mark.skipif(
    not os.path.exists(os.path.join('data', 'raw', 'history_results.parquet')),
    reason='no hay histórico en data/raw (se genera con extract_history.py)',
)
def test_invarianza_con_el_historico_real():
    r = pd.read_parquet(os.path.join('data', 'raw', 'history_results.parquet'))
    q = pd.read_parquet(os.path.join('data', 'raw', 'history_quali.parquet'))
    base = ft.construir_variables(r, q)

    ronda = 10
    r2 = r.copy()
    m = (r2['Year'] == 2024) & (r2['Round'] == ronda)
    r2.loc[m, 'Position'] = r2.loc[m, 'Position'].sample(frac=1, random_state=0).values
    r2.loc[m, 'Points'] = 50
    alterado = ft.construir_variables(r2, q)

    clave = ['Year', 'Round', 'DriverId']
    a = base.set_index(clave)[ft.FEATURES]
    b = alterado.set_index(clave)[ft.FEATURES].loc[a.index]
    cambia = ~((a == b) | (a.isna() & b.isna())).all(axis=1)
    assert min((y, rd) for y, rd, _ in a.index[cambia]) > (2024, ronda)


def test_division_temporal_no_mezcla_pasado_y_futuro():
    d = pd.DataFrame({'Year': [2018, 2023, 2024, 2025, 2026], 'Round': 1, ft.TARGET: 0})
    train, val, test, vivo = ft.dividir_temporal(d)
    assert train['Year'].max() <= 2023 < val['Year'].min()
    assert list(val['Year']) == [2024] and list(test['Year']) == [2025] and list(vivo['Year']) == [2026]
