"""
telemetry.py
Comparación de la vuelta rápida de dos pilotos: telemetría, delta de tiempo,
tramos entre curvas y mapa del circuito por minisectores.

Uso:
    from src.telemetry import comparar_pilotos
    resultado = comparar_pilotos(2024, 'Monza', 'NOR', 'LEC')
"""

import os

import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

CACHE_DIR = 'cache'
FIG_DIR = os.path.join('reports', 'figures')


# ---------- Carga ----------

def cargar_sesion(year, gp, tipo='Q'):
    os.makedirs(CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)
    sesion = fastf1.get_session(year, gp, tipo)
    sesion.load(weather=False, messages=False)
    return sesion


def obtener_curvas(sesion):
    """Curvas del circuito. Si la API de MultiViewer falla, devuelve None y seguimos."""
    try:
        return sesion.get_circuit_info().corners
    except Exception as e:
        print('Sin información de curvas:', e)
        return None


def etiqueta_curva(curva):
    return f"{curva['Number']}{curva['Letter'] or ''}"


# ---------- Cálculos ----------

def calcular_delta(tel_ref, tel_comp, paso=5):
    """Delta acumulado (s) en una malla común de distancia. Positivo: tel_comp va por detrás."""
    fin = min(tel_ref['Distance'].max(), tel_comp['Distance'].max())
    malla = np.arange(0, fin, paso)
    t_ref = np.interp(malla, tel_ref['Distance'], tel_ref['Time'].dt.total_seconds())
    t_comp = np.interp(malla, tel_comp['Distance'], tel_comp['Time'].dt.total_seconds())
    return malla, t_comp - t_ref


def tabla_tramos(malla, delta, curvas, p1):
    """Tiempo que gana p1 en cada tramo entre curvas (negativo: lo gana el otro)."""
    fin = malla[-1]
    if curvas is not None and len(curvas):
        limites = [0] + curvas['Distance'].tolist() + [fin]
        etiquetas = ['Salida'] + [f'C{etiqueta_curva(c)}' for _, c in curvas.iterrows()] + ['Meta']
        nombres = [f'{a} → {b}' for a, b in zip(etiquetas[:-1], etiquetas[1:])]
    else:
        limites = list(np.linspace(0, fin, 11))
        nombres = [f'Tramo {i + 1}' for i in range(10)]

    delta_en = np.interp(limites, malla, delta)
    return pd.DataFrame({
        'tramo': nombres,
        'desde_m': np.round(limites[:-1]),
        'hasta_m': np.round(limites[1:]),
        f'gana_{p1}_s': np.round(np.diff(delta_en), 3),
    })


# ---------- Gráficos ----------

def marcar_curvas(ax, curvas, con_texto=False):
    if curvas is None:
        return
    for _, curva in curvas.iterrows():
        ax.axvline(curva['Distance'], color='gray', linestyle=':', linewidth=0.8)
        if con_texto:
            ax.text(curva['Distance'], ax.get_ylim()[0], etiqueta_curva(curva),
                    ha='center', va='bottom', fontsize=8, color='gray')


def grafico_telemetria(tels, colores, curvas, titulo, archivo):
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True,
                             gridspec_kw={'height_ratios': [3, 1, 1, 1]})
    for piloto, tel in tels.items():
        c = colores[piloto]
        axes[0].plot(tel['Distance'], tel['Speed'], color=c, label=piloto)
        axes[1].plot(tel['Distance'], tel['Throttle'], color=c)
        axes[2].plot(tel['Distance'], tel['Brake'].astype(int), color=c)
        axes[3].plot(tel['Distance'], tel['nGear'], color=c)
    for i, (ax, etiqueta) in enumerate(zip(axes, ['Velocidad (km/h)', 'Acelerador (%)', 'Freno', 'Marcha'])):
        ax.set_ylabel(etiqueta)
        ax.grid(alpha=0.3)
        marcar_curvas(ax, curvas, con_texto=(i == 0))
    axes[0].legend()
    axes[0].set_title(titulo)
    axes[3].set_xlabel('Distancia (m)')
    plt.tight_layout()
    plt.savefig(archivo, dpi=150)
    plt.show()


def grafico_delta(malla, delta, p1, p2, colores, curvas, titulo, archivo):
    fig, ax = plt.subplots(figsize=(15, 5))
    ax.plot(malla, delta, color='black', linewidth=1.5)
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.fill_between(malla, delta, 0, where=delta > 0, color=colores[p1], alpha=0.3, label=f'{p1} por delante')
    ax.fill_between(malla, delta, 0, where=delta < 0, color=colores[p2], alpha=0.3, label=f'{p2} por delante')
    marcar_curvas(ax, curvas, con_texto=True)
    ax.set_xlabel('Distancia (m)')
    ax.set_ylabel('Delta (s)')
    ax.set_title(f'{titulo} · si la línea sube, gana {p1}; si baja, gana {p2}')
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(archivo, dpi=150)
    plt.show()


def mapa_minisectores(tels, p1, p2, colores, titulo, archivo, n=25):
    """Circuito coloreado según quién tiene más velocidad media en cada minisector."""
    fin = min(t['Distance'].max() for t in tels.values())
    bordes = np.linspace(0, fin, n + 1)

    def minisector(tel):
        return pd.cut(tel['Distance'], bordes, labels=False, include_lowest=True)

    velocidad = pd.DataFrame({p: t.groupby(minisector(t))['Speed'].mean() for p, t in tels.items()})
    ganador = (velocidad[p2] > velocidad[p1]).astype(int)        # 0 = p1, 1 = p2

    ref = tels[p1]
    quien = minisector(ref).map(ganador).fillna(0).to_numpy()
    puntos = np.array([ref['X'], ref['Y']]).T.reshape(-1, 1, 2)
    segmentos = np.concatenate([puntos[:-1], puntos[1:]], axis=1)

    lc = LineCollection(segmentos, cmap=ListedColormap([colores[p1], colores[p2]]),
                        norm=plt.Normalize(0, 1), linewidth=6)
    lc.set_array(quien[:-1])

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.add_collection(lc)
    ax.autoscale()
    ax.set_aspect('equal')
    ax.axis('off')
    ax.legend(handles=[
        Line2D([0], [0], color=colores[p1], lw=6, label=f'{p1} más rápido ({(ganador == 0).sum()} minisectores)'),
        Line2D([0], [0], color=colores[p2], lw=6, label=f'{p2} más rápido ({(ganador == 1).sum()} minisectores)'),
    ], loc='upper right')
    ax.set_title(titulo)
    plt.tight_layout()
    plt.savefig(archivo, dpi=150)
    plt.show()


# ---------- Función principal ----------

def comparar_pilotos(year, gp, p1, p2, tipo='Q'):
    """Compara la vuelta más rápida de p1 y p2: 3 gráficos + tabla de tramos."""
    os.makedirs(FIG_DIR, exist_ok=True)
    sesion = cargar_sesion(year, gp, tipo)

    vueltas = {p: sesion.laps.pick_drivers(p).pick_fastest() for p in (p1, p2)}
    tels = {p: v.get_telemetry() for p, v in vueltas.items()}   # incluye X, Y y Distance

    colores = {p: fastf1.plotting.get_driver_color(p, session=sesion) for p in (p1, p2)}
    if colores[p1] == colores[p2]:          # compañeros de equipo: diferenciamos al segundo
        colores[p2] = '#888888'

    curvas = obtener_curvas(sesion)
    diferencia = (vueltas[p2]['LapTime'] - vueltas[p1]['LapTime']).total_seconds()
    titulo = f'{gp} {year} · {tipo} · {p1} vs {p2} ({diferencia:+.3f} s)'
    base = os.path.join(FIG_DIR, f'{year}_{gp}_{tipo}_{p1}_{p2}'.lower().replace(' ', '_'))

    grafico_telemetria(tels, colores, curvas, titulo, base + '_telemetria.png')
    malla, delta = calcular_delta(tels[p1], tels[p2])
    grafico_delta(malla, delta, p1, p2, colores, curvas, titulo, base + '_delta.png')
    mapa_minisectores(tels, p1, p2, colores, titulo, base + '_mapa.png')

    tramos = tabla_tramos(malla, delta, curvas, p1)
    tramos.to_csv(base + '_tramos.csv', index=False)

    return {'sesion': sesion, 'telemetria': tels, 'malla': malla, 'delta': delta,
            'tramos': tramos, 'diferencia': diferencia}