"""
powerbi_export.py
Construye un MODELO EN ESTRELLA para Power BI (o Tableau) a partir de los datos del proyecto
y lo guarda en data/processed/powerbi/ como CSV y como un único Excel con una tabla por hoja.

Modelo en estrella: unas pocas tablas de HECHOS (eventos medibles: una vuelta, un resultado,
una predicción) rodeadas de tablas de DIMENSIONES (quién, dónde, cuándo: pilotos, equipos,
carreras, calendario). Los hechos se unen a las dimensiones por una CLAVE. Ventajas en Power BI:
filtros que se propagan solos, medidas DAX sencillas y menos duplicación de datos.

Convenciones:
- Claves: CarreraId = año*100 + ronda (p. ej. 202416 = ronda 16 de 2024), PilotoId = driverId de
  Jolpica (p. ej. 'max_verstappen'), EquipoId = constructorId (p. ej. 'red_bull').
- Una columna llamada ...Id es una clave. Los nombres de columnas van en español y sin espacios.
- Fechas en ISO (AAAA-MM-DD), decimales con punto, texto en UTF-8.

Uso (desde la raíz del proyecto):
    python src/powerbi_export.py
"""

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as ft          # noqa: E402
import model as md             # noqa: E402
import strategy as st          # noqa: E402

RAW = os.path.join('data', 'raw')
PROC = os.path.join('data', 'processed')
SALIDA = os.path.join(PROC, 'powerbi')

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# Colores oficiales de Pirelli (los mismos que en los notebooks)
COMPUESTOS = pd.DataFrame({
    'Compuesto': ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET', 'DESCONOCIDO'],
    'OrdenCompuesto': [1, 2, 3, 4, 5, 6],
    'TipoNeumatico': ['Seco'] * 3 + ['Mojado'] * 2 + ['Desconocido'],
    'ColorHex': ['#DA291C', '#FFD12E', '#F0F0EC', '#43B02A', '#0067AD', '#898781'],
})
# 'DESCONOCIDO' es el "miembro desconocido" de la dimensión: FastF1 a veces no trae el compuesto de una vuelta
# (llega como NaN o como el texto 'None'). Así la vuelta se conserva y la relación con la dimensión no queda rota.

# La telemetría usa el nombre corto del circuito; se traduce al nombre oficial del GP
GP_CORTO = {'Monaco': 'Monaco Grand Prix', 'Monza': 'Italian Grand Prix', 'Suzuka': 'Japanese Grand Prix'}


def carrera_id(anio, ronda):
    return (anio * 100 + ronda).astype(int)


# ---------------------------------------------------------------------------
# Dimensiones
# ---------------------------------------------------------------------------

def dim_calendario(desde='2018-01-01', hasta='2026-12-31'):
    """Tabla de fechas: una fila por día. Power BI la necesita para las funciones de inteligencia de tiempo."""
    f = pd.DataFrame({'Fecha': pd.date_range(desde, hasta, freq='D')})
    f['Anio'] = f['Fecha'].dt.year
    f['Mes'] = f['Fecha'].dt.month
    f['NombreMes'] = f['Mes'].map(lambda m: MESES[m - 1])
    f['Trimestre'] = 'T' + f['Fecha'].dt.quarter.astype(str)
    f['AnioMes'] = f['Fecha'].dt.strftime('%Y-%m')
    f['Fecha'] = f['Fecha'].dt.strftime('%Y-%m-%d')
    return f


def dim_carrera(hist):
    c = (hist[['Year', 'Round', 'Event', 'Date', 'CircuitId']].drop_duplicates()
         .rename(columns={'Year': 'Anio', 'Round': 'Ronda', 'Event': 'GranPremio',
                          'Date': 'Fecha', 'CircuitId': 'CircuitoId'}))
    c.insert(0, 'CarreraId', carrera_id(c['Anio'], c['Ronda']))
    # etiqueta para ejes y segmentaciones: '2024 R16 · Italian Grand Prix'
    c['Etiqueta'] = c['Anio'].astype(str) + ' R' + c['Ronda'].astype(str).str.zfill(2) + ' · ' + c['GranPremio']
    return c.sort_values('CarreraId').reset_index(drop=True)


def dim_piloto(hist):
    """Una fila por piloto, con su abreviatura, nombre y nacionalidad más recientes."""
    h = hist.sort_values(['Year', 'Round'])
    p = (h.groupby('DriverId').agg(Abreviatura=('Abbreviation', 'last'), Piloto=('DriverName', 'last'),
                                   Nacionalidad=('Nationality', 'last')).reset_index()
         .rename(columns={'DriverId': 'PilotoId'}))
    return p.sort_values('Piloto').reset_index(drop=True)


def dim_equipo(hist):
    h = hist.sort_values(['Year', 'Round'])
    e = (h.groupby('TeamId').agg(Equipo=('TeamName', 'last')).reset_index().rename(columns={'TeamId': 'EquipoId'}))
    return e.sort_values('Equipo').reset_index(drop=True)


# ---------------------------------------------------------------------------
# Hechos
# ---------------------------------------------------------------------------

def fact_resultados(datos):
    """Un resultado por piloto y carrera (2018-2026)."""
    f = pd.DataFrame({
        'CarreraId': carrera_id(datos['Year'], datos['Round']),
        'PilotoId': datos['DriverId'], 'EquipoId': datos['TeamId'],
        'Posicion': datos['Position'], 'Parrilla': datos['Grid'], 'ParrillaAj': datos['GridAdj'],
        'Puntos': datos['Points'], 'Podio': datos['Podio'], 'Victoria': (datos['Position'] == 1).astype(int),
        'Abandono': md.abandono(datos).astype(int), 'Estado': datos['Status'], 'Vueltas': datos['Laps'],
        'PosicionesGanadas': datos['GridAdj'] - datos['Position'], 'DifPolePct': datos['DifPolePct'].round(3),
    })
    return f.sort_values(['CarreraId', 'Posicion']).reset_index(drop=True)


def mapa_pilotos():
    """
    (año, ronda, abreviatura) -> PilotoId y EquipoId, a partir del histórico de Jolpica. Se usa el histórico y no
    los archivos brutos de FastF1 porque el histórico siempre se regenera (también en GitHub Actions).
    """
    h = pd.read_parquet(os.path.join(RAW, 'history_results.parquet'))
    return (h[['Year', 'Round', 'Abbreviation', 'DriverId', 'TeamId']]
            .drop_duplicates(['Year', 'Round', 'Abbreviation']))


def fact_vueltas():
    """
    Vueltas limpias de todos los años disponibles (laps_clean_*.parquet), con el tiempo corregido por combustible.
    La corrección se hace año por año porque 'Round' se repite entre temporadas.
    """
    partes = []
    for ruta in sorted(glob.glob(os.path.join(PROC, 'laps_clean_*.parquet'))):
        partes.append(st.corregir_combustible(pd.read_parquet(ruta)))
    v = pd.concat(partes, ignore_index=True)
    v = v.merge(mapa_pilotos(), left_on=['Year', 'Round', 'Driver'], right_on=['Year', 'Round', 'Abbreviation'], how='left')
    return pd.DataFrame({
        'CarreraId': carrera_id(v['Year'], v['Round']), 'PilotoId': v['DriverId'], 'EquipoId': v['TeamId'],
        'Vuelta': v['LapNumber'].astype(int), 'Stint': v['Stint'].astype('Int64'),
        'Compuesto': v['Compound'].where(v['Compound'].isin(COMPUESTOS['Compuesto']), 'DESCONOCIDO'),
        # Int64 admite vacíos (hay vueltas sin dato de neumático)
        'VidaNeumatico': v['TyreLife'].astype('Int64'), 'TiempoVueltaSeg': v['LapTimeSec'].round(3),
        'TiempoCorregidoSeg': v['LapTimeCorr'].round(3), 'Sector1Seg': v['Sector1Sec'].round(3),
        'Sector2Seg': v['Sector2Sec'].round(3), 'Sector3Seg': v['Sector3Sec'].round(3),
        'Lluvia': v['Lluvia'].astype(int), 'TempPista': v['TrackTemp'], 'TempAire': v['AirTemp'],
    }).reset_index(drop=True)


def _gp_a_carrera(nombres, anio=2024):
    """Convierte el nombre del GP en CarreraId usando el calendario del histórico."""
    h = pd.read_parquet(os.path.join(RAW, 'history_results.parquet'))
    h = h[h['Year'] == anio][['Round', 'Event']].drop_duplicates()
    m = dict(zip(h['Event'], anio * 100 + h['Round']))
    return nombres.map(m)


def fact_estrategias():
    e = pd.read_csv(os.path.join(PROC, 'estrategias_vs_optima_2024.csv'))
    e['CarreraId'] = _gp_a_carrera(e['gp'])
    pil = mapa_pilotos().query('Year == 2024').assign(CarreraId=lambda d: d['Year'] * 100 + d['Round'])
    e = e.merge(pil, left_on=['CarreraId', 'piloto'], right_on=['CarreraId', 'Abbreviation'], how='left')
    return pd.DataFrame({
        'CarreraId': e['CarreraId'], 'PilotoId': e['DriverId'], 'EquipoId': e['TeamId'],
        'PosicionFinal': e['posicion'], 'Estrategia': e['estrategia_real'], 'Paradas': e['paradas'],
        'VsOptimaSeg': e['vs_optima_s'],
    }).reset_index(drop=True)


def fact_degradacion():
    d = pd.read_csv(os.path.join(PROC, 'degradacion_stints_2024.csv'))
    d = d.merge(mapa_pilotos().query('Year == 2024'), left_on=['Round', 'Driver'], right_on=['Round', 'Abbreviation'], how='left')
    return pd.DataFrame({
        'CarreraId': 202400 + d['Round'], 'PilotoId': d['DriverId'], 'EquipoId': d['TeamId'],
        'Stint': d['Stint'].astype(int), 'Compuesto': d['Compound'], 'Vueltas': d['vueltas'].astype(int),
        'DegradacionSegVuelta': d['degradacion_s'].round(4),
    }).reset_index(drop=True)


def tiempo_oficial_duelo(carrera_id_, p1, p2):
    """
    Diferencia OFICIAL de vuelta entre dos pilotos (segundos; positivo = gana el piloto 1), calculada con su
    mejor tiempo de clasificación (Jolpica). Es la referencia fiable: la telemetría integra la distancia de
    cada piloto de forma ligeramente distinta y su suma de tramos no siempre coincide con el cronómetro.
    """
    q = pd.read_parquet(os.path.join(RAW, 'history_quali.parquet'))
    q = q[(q['Year'] * 100 + q['Round']) == carrera_id_].set_index('DriverId')
    mejor = q[['Q1', 'Q2', 'Q3']].apply(lambda c: c.map(ft.tiempo_a_segundos)).min(axis=1)
    return round(mejor[p2] - mejor[p1], 3)


def fact_telemetria():
    """
    Tramos entre curvas de los duelos de clasificación de Mónaco, Monza y Suzuka (2024).
    GanaP1CrudoSeg es lo que mide la telemetría; GanaP1Seg es esa medida AJUSTADA para que la suma de
    los tramos coincida con la diferencia oficial de vuelta (DifOficialSeg). El residuo se reparte en
    proporción a la longitud de cada tramo, suponiendo que el error de integración crece con la distancia.
    """
    t = pd.read_csv(os.path.join(PROC, 'telemetria_tramos.csv'))
    t['GranPremio'] = t['gp'].map(GP_CORTO)
    t['CarreraId'] = _gp_a_carrera(t['GranPremio'])
    pil = mapa_pilotos().query('Year == 2024').assign(CarreraId=lambda d: 202400 + d['Round'])
    for n in (1, 2):
        t = (t.merge(pil[['CarreraId', 'Abbreviation', 'DriverId']].rename(columns={'DriverId': f'Piloto{n}Id'}),
                     left_on=['CarreraId', f'piloto_{n}'], right_on=['CarreraId', 'Abbreviation'])
             .drop(columns='Abbreviation'))
    t['OrdenTramo'] = t.groupby(['CarreraId', 'piloto_1', 'piloto_2']).cumcount() + 1
    t['LongitudM'] = t['hasta_m'] - t['desde_m']
    grupo = ['CarreraId', 'Piloto1Id', 'Piloto2Id']
    t['DifOficialSeg'] = [tiempo_oficial_duelo(c, a, b) for c, a, b in zip(t['CarreraId'], t['Piloto1Id'], t['Piloto2Id'])]
    residuo = t['DifOficialSeg'] - t.groupby(grupo)['gana_p1_s'].transform('sum')
    t['GanaP1Seg'] = t['gana_p1_s'] + residuo * t['LongitudM'] / t.groupby(grupo)['LongitudM'].transform('sum')
    return pd.DataFrame({
        'CarreraId': t['CarreraId'], 'Sesion': 'Clasificación', 'Piloto1Id': t['Piloto1Id'], 'Piloto2Id': t['Piloto2Id'],
        'Duelo': t['piloto_1'] + ' vs ' + t['piloto_2'], 'OrdenTramo': t['OrdenTramo'], 'Tramo': t['tramo'],
        'DesdeM': t['desde_m'], 'HastaM': t['hasta_m'], 'LongitudM': t['LongitudM'],
        'GanaP1CrudoSeg': t['gana_p1_s'], 'GanaP1Seg': t['GanaP1Seg'].round(4), 'DifOficialSeg': t['DifOficialSeg'],
    }).reset_index(drop=True)


def fact_predicciones(hist):
    p = pd.read_csv(os.path.join(PROC, 'predicciones_podio.csv'))
    equipo = hist[['Year', 'Round', 'DriverId', 'TeamId']]
    p = p.merge(equipo, on=['Year', 'Round', 'DriverId'], how='left')
    return pd.DataFrame({
        'CarreraId': carrera_id(p['Year'], p['Round']), 'PilotoId': p['DriverId'], 'EquipoId': p['TeamId'],
        'Conjunto': np.where(p['Year'] == 2025, 'Test 2025', 'En vivo ' + p['Year'].astype(str)), 'Modelo': p['Modelo'],
        'ParrillaAj': p['GridAdj'], 'ProbaPodio': p['Proba'].round(4), 'ProbaPodioNorm': p['ProbaNorm'].round(4),
        'RankProba': p['RankProba'], 'PredPodio': p['PredPodio'], 'PredTrivial': (p['GridAdj'] <= 3).astype(int),
        'PosicionReal': p['PosicionReal'], 'PodioReal': p['PodioReal'],
        'Acierto': ((p['PredPodio'] == 1) & (p['PodioReal'] == 1)).astype(int),
    }).sort_values(['CarreraId', 'RankProba']).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Construcción, validación y exportación
# ---------------------------------------------------------------------------

# tabla -> (columna clave primaria, o None si es de hechos)
CLAVES = {'dim_calendario': 'Fecha', 'dim_carrera': 'CarreraId', 'dim_piloto': 'PilotoId',
          'dim_equipo': 'EquipoId', 'dim_compuesto': 'Compuesto'}

# (tabla de hechos, columna, dimensión): relaciones de muchos a uno
RELACIONES = [
    ('dim_carrera', 'Fecha', 'dim_calendario'),
    ('fact_resultados', 'CarreraId', 'dim_carrera'), ('fact_resultados', 'PilotoId', 'dim_piloto'), ('fact_resultados', 'EquipoId', 'dim_equipo'),
    ('fact_vueltas', 'CarreraId', 'dim_carrera'), ('fact_vueltas', 'PilotoId', 'dim_piloto'), ('fact_vueltas', 'EquipoId', 'dim_equipo'),
    ('fact_vueltas', 'Compuesto', 'dim_compuesto'),
    ('fact_estrategias', 'CarreraId', 'dim_carrera'), ('fact_estrategias', 'PilotoId', 'dim_piloto'), ('fact_estrategias', 'EquipoId', 'dim_equipo'),
    ('fact_degradacion', 'CarreraId', 'dim_carrera'), ('fact_degradacion', 'PilotoId', 'dim_piloto'), ('fact_degradacion', 'EquipoId', 'dim_equipo'),
    ('fact_degradacion', 'Compuesto', 'dim_compuesto'),
    ('fact_telemetria_tramos', 'CarreraId', 'dim_carrera'), ('fact_telemetria_tramos', 'Piloto1Id', 'dim_piloto'),
    ('fact_telemetria_tramos', 'Piloto2Id', 'dim_piloto'),
    ('fact_predicciones', 'CarreraId', 'dim_carrera'), ('fact_predicciones', 'PilotoId', 'dim_piloto'), ('fact_predicciones', 'EquipoId', 'dim_equipo'),
]


def construir_modelo():
    datos = ft.cargar_datos()
    hist = pd.read_parquet(os.path.join(RAW, 'history_results.parquet'))
    return {
        'dim_calendario': dim_calendario(), 'dim_carrera': dim_carrera(hist), 'dim_piloto': dim_piloto(hist),
        'dim_equipo': dim_equipo(hist), 'dim_compuesto': COMPUESTOS.copy(),
        'fact_resultados': fact_resultados(datos), 'fact_vueltas': fact_vueltas(),
        'fact_estrategias': fact_estrategias(), 'fact_degradacion': fact_degradacion(),
        'fact_telemetria_tramos': fact_telemetria(), 'fact_predicciones': fact_predicciones(hist),
    }


def validar(tablas):
    """Integridad referencial: claves únicas en las dimensiones, sin nulos y sin claves huérfanas en los hechos."""
    errores = []
    for tabla, clave in CLAVES.items():
        s = tablas[tabla][clave]
        if s.isna().any():
            errores.append(f'{tabla}.{clave}: hay claves vacías')
        if s.duplicated().any():
            errores.append(f'{tabla}.{clave}: {s.duplicated().sum()} claves duplicadas')
    for origen, col, dim in RELACIONES:
        s = tablas[origen][col]
        if s.isna().any():
            errores.append(f'{origen}.{col}: {s.isna().sum()} valores vacíos')
        huerfanas = ~s.dropna().isin(tablas[dim][CLAVES[dim]])
        if huerfanas.any():
            errores.append(f'{origen}.{col}: {huerfanas.sum()} claves que no existen en {dim}')
    # en resultados no puede haber dos filas del mismo piloto en la misma carrera
    if tablas['fact_resultados'].duplicated(['CarreraId', 'PilotoId']).any():
        errores.append('fact_resultados: piloto repetido en una carrera')
    if tablas['fact_predicciones'].duplicated(['CarreraId', 'PilotoId']).any():
        errores.append('fact_predicciones: piloto repetido en una carrera')
    return errores


def exportar(tablas):
    os.makedirs(SALIDA, exist_ok=True)
    for nombre, df in tablas.items():
        df.to_csv(os.path.join(SALIDA, f'{nombre}.csv'), index=False, encoding='utf-8-sig')  # BOM: Excel/Power BI leen bien las tildes
    # Un solo Excel con cada tabla como "Tabla de Excel" (Power BI web solo importa tablas con nombre)
    ruta = os.path.join(SALIDA, 'modelo_f1.xlsx')
    # En el Excel las fechas se guardan como fechas reales: en Power BI web no siempre se puede cambiar el tipo después
    with pd.ExcelWriter(ruta, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as w:
        for nombre, df in tablas.items():
            df = df.assign(**{c: pd.to_datetime(df[c]) for c in df.columns if c == 'Fecha'})
            df.to_excel(w, sheet_name=nombre, index=False, startrow=0)
            filas, cols = df.shape
            w.sheets[nombre].add_table(0, 0, max(filas, 1), cols - 1, {
                'name': nombre, 'columns': [{'header': c} for c in df.columns], 'style': 'Table Style Light 9'})


if __name__ == '__main__':
    tablas = construir_modelo()
    errores = validar(tablas)
    for n, d in tablas.items():
        print(f'{n:<24}{len(d):>8} filas · {d.shape[1]:>2} columnas')
    if errores:
        print('\nERRORES DE INTEGRIDAD:')
        print('\n'.join(f' - {e}' for e in errores))
        raise SystemExit(1)
    exportar(tablas)
    print(f'\nIntegridad OK. Exportado en {SALIDA}/')
