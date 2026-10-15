"""
features.py
Ingeniería de variables para predecir si un piloto acaba en el podio.

REGLA DE ORO: cada variable de una carrera solo puede usar información que ya
existía ANTES de que empezase esa carrera. Para conseguirlo, los acumulados y las
medias móviles se calculan con shift(1) dentro de cada grupo (piloto, equipo o
circuito): shift(1) desplaza la serie una fila hacia abajo, de modo que cada fila
ve el valor de la carrera anterior y nunca el suyo.

Uso (desde la raíz del proyecto):
    python src/features.py
"""

import os

import numpy as np
import pandas as pd

RAW_DIR = os.path.join('data', 'raw')
OUTPUT_DIR = os.path.join('data', 'processed')

GRID_PIT_LANE = 20  # Grid == 0 significa salida desde el pit lane: se trata como la 20ª posición

# Variables que usa el modelo (todas conocidas antes de la salida)
FEATURES = [
    'GridAdj',  # posición de salida (pit lane = 20)
    'PuntosPilotoAntes',  # puntos del piloto en la temporada antes de esta carrera
    'PuntosEquipoAntes',  # puntos del equipo en la temporada antes de esta carrera
    'MediaUlt3',  # media de posiciones finales en las 3 últimas carreras
    'PosCircuitoPrevia',  # posición final la última vez que corrió en este circuito
    'DifPolePct',  # % de diferencia con la pole en clasificación
]
TARGET = 'Podio'


def tiempo_a_segundos(texto):
    """
    Convierte '1:19.507' en 79.507 segundos. Devuelve NaN si no hay tiempo.
    También admite vueltas de menos de un minuto sin 'm:' (p. ej. '54.309' en Mónaco).
    """
    if texto is None or pd.isna(texto) or texto == '':
        return np.nan
    *minutos, segundos = str(texto).split(':')
    return (int(minutos[0]) * 60 if minutos else 0) + float(segundos)


def diferencia_con_pole(quali):
    """
    % de diferencia de cada piloto con la pole de su carrera.
    Se usa la MEJOR vuelta de cada piloto entre Q1, Q2 y Q3 (la pole siempre sale de Q3).
    Quien cae en Q1 solo tiene tiempo de Q1, así que su diferencia incluye también
    la mejora de la pista durante la sesión: se asume como parte de 'ser más lento'.
    """
    q = quali.copy()
    tiempos = q[['Q1', 'Q2', 'Q3']].apply(lambda col: col.map(tiempo_a_segundos))
    q['MejorQuali'] = tiempos.min(axis=1)  # NaN si no marcó tiempo
    pole = q.groupby(['Year', 'Round'])['MejorQuali'].transform('min')
    q['DifPolePct'] = (q['MejorQuali'] - pole) / pole * 100
    return q[['Year', 'Round', 'DriverId', 'QualiPosition', 'DifPolePct']]


def construir_variables(resultados, quali):
    """
    Devuelve una fila por piloto y carrera con el objetivo (Podio) y las variables.
    Todo se ordena cronológicamente antes de calcular nada.
    """
    df = resultados.sort_values(['Year', 'Round', 'Position']).reset_index(drop=True)
    df = df.merge(diferencia_con_pole(quali), on=['Year', 'Round', 'DriverId'], how='left')

    # Objetivo: ¿terminó entre los 3 primeros?
    df[TARGET] = (df['Position'] <= 3).astype(int)

    # 1) Salida: el pit lane (Grid == 0) cuenta como última posición
    df['GridAdj'] = df['Grid'].replace(0, GRID_PIT_LANE)

    # 2) Puntos del piloto antes de la carrera: acumulado de la temporada menos los de hoy
    #    (equivale a cumsum().shift(1) pero sin perder la primera fila del grupo)
    df['PuntosPilotoAntes'] = df.groupby(['Year', 'DriverId'])['Points'].cumsum() - df['Points']

    # 3) Puntos del equipo antes de la carrera: primero los puntos que suma el equipo en
    #    cada carrera (los dos pilotos), luego el acumulado de la temporada con shift(1)
    equipo = (
        df.groupby(['Year', 'Round', 'TeamId'], as_index=False)['Points'].sum().sort_values(['Year', 'TeamId', 'Round'])
    )
    equipo['PuntosEquipoAntes'] = equipo.groupby(['Year', 'TeamId'])['Points'].cumsum() - equipo['Points']
    df = df.merge(equipo[['Year', 'Round', 'TeamId', 'PuntosEquipoAntes']], on=['Year', 'Round', 'TeamId'], how='left')

    # 4) Media de las 3 últimas posiciones: shift(1) y luego media móvil de 3.
    #    Continúa entre temporadas; para un debutante queda NaN (se imputa en el modelo).
    df['MediaUlt3'] = df.groupby('DriverId')['Position'].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )

    # 5) Resultado la última vez que el piloto corrió en ese circuito (normalmente, el año anterior)
    df['PosCircuitoPrevia'] = df.groupby(['DriverId', 'CircuitId'])['Position'].shift(1)

    return df


def cargar_datos():
    """Lee el histórico descargado con extract_history.py y construye las variables."""
    resultados = pd.read_parquet(os.path.join(RAW_DIR, 'history_results.parquet'))
    quali = pd.read_parquet(os.path.join(RAW_DIR, 'history_quali.parquet'))
    return construir_variables(resultados, quali)


def dividir_temporal(df, fin_train=2023, validacion=2024, test=2025):
    """
    División TEMPORAL (no aleatoria): entrenar con el pasado, validar y testear con el futuro.
    Las temporadas posteriores al test (2026) quedan fuera, reservadas para predicciones 'en vivo'.
    """
    train = df[df['Year'] <= fin_train]
    val = df[df['Year'] == validacion]
    prueba = df[df['Year'] == test]
    vivo = df[df['Year'] > test]
    return train, val, prueba, vivo


if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    datos = cargar_datos()
    ruta = os.path.join(OUTPUT_DIR, 'features_podio.parquet')
    datos.to_parquet(ruta)
    print(f'Guardado {ruta}: {datos.shape[0]} filas, {datos[TARGET].mean():.1%} podios')
    print(datos[FEATURES].describe().round(2).T)
