"""
strategy.py
Fase 3: corrección por combustible, modelo de degradación y simulador de estrategia.

Uso:
    from src.strategy import analizar_carrera
    r = analizar_carrera('Italian Grand Prix', vueltas, limpias, resultados)
"""

from itertools import product

import numpy as np
import pandas as pd

# --- Supuestos (documentados en el notebook) ---
KG_COMBUSTIBLE = 100      # combustible aproximado al inicio
S_POR_KG = 0.03           # segundos por vuelta que cuesta cada kg
MIN_VUELTAS_AJUSTE = 6    # vueltas mínimas de un stint para ajustar su recta
MIN_STINT = 5             # longitud mínima de un stint en el simulador
SECOS = ['SOFT', 'MEDIUM', 'HARD']


def corregir_combustible(df):
    df = df.copy()
    total = df.groupby('Round')['LapNumber'].transform('max')
    penalizacion = S_POR_KG * KG_COMBUSTIBLE / total
    df['VueltasRestantes'] = total - df['LapNumber']
    df['LapTimeCorr'] = df['LapTimeSec'] - penalizacion * df['VueltasRestantes']
    return df


def ajuste(g):
    """Recta de un stint: ritmo base (ordenada) y degradación (pendiente)."""
    if len(g) < MIN_VUELTAS_AJUSTE:
        return pd.Series({'base': np.nan, 'deg': np.nan})
    deg, base = np.polyfit(g['TyreLife'], g['LapTimeCorr'], 1)
    return pd.Series({'base': base, 'deg': deg})


def modelo_neumaticos(limpias_gp):
    """Mediana del ritmo base y la degradación de cada compuesto de seco."""
    secos = limpias_gp[limpias_gp['Compound'].isin(SECOS) & ~limpias_gp['Lluvia']]
    return (secos.groupby(['Driver', 'Stint', 'Compound'])
            .apply(ajuste, include_groups=False)
            .dropna()
            .groupby('Compound')[['base', 'deg']]
            .median())


def stints_carrera(vueltas_gp):
    return (vueltas_gp.groupby(['Driver', 'Stint', 'Compound'], as_index=False)
            .agg(inicio=('LapNumber', 'min'), fin=('LapNumber', 'max')))


def perdida_box(vueltas_gp, limpias_gp, por_defecto=22.0):
    """Mediana del tiempo perdido por parada con bandera verde (vuelta de entrada + salida)."""
    c = vueltas_gp.sort_values(['Driver', 'LapNumber']).copy()
    c['LapSec'] = c['LapTime'].dt.total_seconds()
    c['SiguienteSec'] = c.groupby('Driver')['LapSec'].shift(-1)
    ritmo = limpias_gp.groupby('Driver')['LapTimeSec'].median()
    p = c[c['PitInTime'].notna() & c['SiguienteSec'].notna() & (c['TrackStatus'] == '1')]
    perdida = (p['LapSec'] + p['SiguienteSec'] - 2 * p['Driver'].map(ritmo)).median()
    return por_defecto if pd.isna(perdida) else perdida


def tiempo_estrategia(estrategia, modelo, perdida):
    total = 0.0
    for compuesto, vueltas in estrategia:
        base, deg = modelo.loc[compuesto, ['base', 'deg']]
        total += (base + deg * np.arange(1, vueltas + 1)).sum()
    return total + (len(estrategia) - 1) * perdida


def generar_candidatas(total, compuestos, min_stint=MIN_STINT):
    candidatas = []
    for c1, c2 in product(compuestos, repeat=2):
        if c1 != c2:
            for l1 in range(min_stint, total - min_stint + 1):
                candidatas.append([(c1, l1), (c2, total - l1)])
    for c1, c2, c3 in product(compuestos, repeat=3):
        if len({c1, c2, c3}) >= 2:
            for l1 in range(min_stint, total - 2 * min_stint + 1):
                for l2 in range(min_stint, total - l1 - min_stint + 1):
                    candidatas.append([(c1, l1), (c2, l2), (c3, total - l1 - l2)])
    return candidatas


def describir(estrategia):
    return ' → '.join(f'{c[0]}{v}' for c, v in estrategia)


def estrategia_real(stints, piloto):
    s = stints[stints['Driver'] == piloto].sort_values('Stint')
    return [(r['Compound'], int(r['fin'] - r['inicio'] + 1)) for _, r in s.iterrows()]


def analizar_carrera(gp, vueltas, limpias, resultados, top=10):
    """Modelo, estrategia óptima y comparación con las estrategias reales del top."""
    v = vueltas[vueltas['Event'] == gp]
    l = corregir_combustible(limpias[limpias['Event'] == gp])

    modelo = modelo_neumaticos(l)
    perdida = perdida_box(v, l)
    total = int(v['LapNumber'].max())

    candidatas = generar_candidatas(total, modelo.index.tolist())
    tiempos = [tiempo_estrategia(e, modelo, perdida) for e in candidatas]
    ranking = pd.DataFrame({
        'estrategia': [describir(e) for e in candidatas],
        'paradas': [len(e) - 1 for e in candidatas],
        'tiempo_s': tiempos,
    }).sort_values('tiempo_s').reset_index(drop=True)
    mejor = ranking['tiempo_s'].iloc[0]

    stints = stints_carrera(v)
    pilotos = (resultados[resultados['Event'] == gp]
               .sort_values('Position')['Abbreviation'].head(top))
    filas = []
    for pos, piloto in enumerate(pilotos, start=1):
        e = estrategia_real(stints, piloto)
        modelable = len(e) > 0 and all(c in modelo.index for c, _ in e)
        filas.append({
            'gp': gp, 'posicion': pos, 'piloto': piloto,
            'estrategia_real': describir(e), 'paradas': len(e) - 1,
            'vs_optima_s': round(tiempo_estrategia(e, modelo, perdida) - mejor, 1) if modelable else np.nan,
        })

    return {'modelo': modelo, 'perdida_box': perdida, 'ranking': ranking,
            'optima': ranking.iloc[0]['estrategia'], 'reales': pd.DataFrame(filas)}