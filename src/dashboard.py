"""
dashboard.py
Genera reports/dashboard.html: un informe interactivo y autocontenido (sin servidor) con 4 secciones:
resumen de temporada, telemetría, estrategia y predicciones. Es el respaldo de Power BI y una pieza
para el portfolio.

Lee las MISMAS tablas del modelo en estrella (data/processed/powerbi/*.csv), así que las cifras
coinciden con las del informe de Power BI. Los datos se incrustan en el HTML como JSON y los gráficos
se dibujan con Plotly.js en el navegador; el filtrado (año, duelo, GP...) lo hace JavaScript.

Uso (desde la raíz del proyecto):
    python src/dashboard.py
"""

import json
import os
import re

import pandas as pd
from plotly.offline import get_plotlyjs

STAR = os.path.join('data', 'processed', 'powerbi')
PLANTILLA = os.path.join('src', 'templates', 'dashboard.html')
SALIDA = os.path.join('reports', 'dashboard.html')

# Nombre corto de cada mapa de minisectores generado en la Fase 2 (reports/figures/)
MAPAS = {'Monza': '2024_monza_q_nor_lec_mapa.png', 'Monaco': '2024_monaco_q_lec_pia_mapa.png',
         'Suzuka': '2024_suzuka_q_ver_nor_mapa.png'}
CIRCUITO = {202416: 'Monza', 202408: 'Monaco', 202404: 'Suzuka'}


def tabla(nombre):
    return pd.read_csv(os.path.join(STAR, f'{nombre}.csv'), encoding='utf-8-sig')


def a_columnas(df):
    """DataFrame -> dict de listas (formato compacto para JSON). Los NaN pasan a null."""
    return {c: df[c].astype(object).where(df[c].notna(), None).tolist() for c in df.columns}


def parsear_estrategia(texto):
    """'M15 → H38' -> [['MEDIUM', 15], ['HARD', 38]]"""
    nombres = {'S': 'SOFT', 'M': 'MEDIUM', 'H': 'HARD', 'I': 'INTERMEDIATE', 'W': 'WET'}
    return [[nombres[m[0]], int(m[1:])] for m in re.findall(r'[SMHIW]\d+', texto)]


def construir_datos():
    carrera = tabla('dim_carrera').set_index('CarreraId')
    piloto = tabla('dim_piloto').set_index('PilotoId')
    equipo = tabla('dim_equipo').set_index('EquipoId')

    def con_dims(df):
        df = df.copy()
        df['Piloto'] = df['PilotoId'].map(piloto['Piloto'])
        df['Abrev'] = df['PilotoId'].map(piloto['Abreviatura'])
        df['Equipo'] = df['EquipoId'].map(equipo['Equipo'])
        df['Anio'] = df['CarreraId'] // 100
        df['Ronda'] = df['CarreraId'] % 100
        df['GP'] = df['CarreraId'].map(carrera['GranPremio'])
        return df

    res = con_dims(tabla('fact_resultados'))[['Anio', 'Ronda', 'GP', 'Piloto', 'Abrev', 'Equipo', 'Posicion',
                                              'Parrilla', 'Puntos', 'Podio', 'Victoria', 'Abandono']]
    pred = con_dims(tabla('fact_predicciones'))[['CarreraId', 'Anio', 'Ronda', 'GP', 'Piloto', 'Abrev', 'Equipo',
                                                 'Conjunto', 'ParrillaAj', 'ProbaPodioNorm', 'RankProba',
                                                 'PredPodio', 'PredTrivial', 'PosicionReal', 'PodioReal', 'Acierto']]

    # Vueltas: solo los 3 GP con análisis de estrategia (mantiene el HTML ligero)
    est = con_dims(tabla('fact_estrategias'))
    est['Segmentos'] = est['Estrategia'].map(parsear_estrategia)
    gps = est['CarreraId'].unique()
    vue = con_dims(tabla('fact_vueltas'))
    vue = vue[vue['CarreraId'].isin(gps)][['CarreraId', 'Abrev', 'Compuesto', 'VidaNeumatico', 'TiempoCorregidoSeg']]
    deg = tabla('fact_degradacion')
    deg = deg[deg['CarreraId'].isin(gps)][['CarreraId', 'Compuesto', 'Vueltas', 'DegradacionSegVuelta']]

    tel = tabla('fact_telemetria_tramos')
    tel['Circuito'] = tel['CarreraId'].map(CIRCUITO)
    tel['Mapa'] = 'figures/' + tel['Circuito'].map(MAPAS)

    return {
        'resultados': a_columnas(res),
        'predicciones': a_columnas(pred),
        'estrategias': a_columnas(est[['CarreraId', 'GP', 'Abrev', 'Equipo', 'PosicionFinal', 'Estrategia',
                                       'Paradas', 'VsOptimaSeg', 'Segmentos']]),
        'vueltas': a_columnas(vue), 'degradacion': a_columnas(deg),
        'telemetria': a_columnas(tel[['CarreraId', 'Circuito', 'Duelo', 'OrdenTramo', 'Tramo', 'DesdeM', 'HastaM',
                                      'LongitudM', 'GanaP1Seg', 'GanaP1CrudoSeg', 'DifOficialSeg', 'Mapa']]),
        'compuestos': a_columnas(tabla('dim_compuesto')),
    }


def generar():
    """Escribe reports/dashboard.html a partir de la plantilla y de las tablas del modelo en estrella."""
    datos = construir_datos()
    html = open(PLANTILLA, encoding='utf-8').read()
    html = html.replace('/*PLOTLY*/', get_plotlyjs())
    html = html.replace('/*DATOS*/', json.dumps(datos, ensure_ascii=False, separators=(',', ':')))
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Guardado {SALIDA}: {os.path.getsize(SALIDA) / 1e6:.1f} MB')


if __name__ == '__main__':
    generar()
