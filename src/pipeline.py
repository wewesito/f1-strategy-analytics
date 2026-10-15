"""
pipeline.py
Pipeline de actualización: encadena todas las etapas del proyecto para UN año y descarga solo las carreras nuevas.

Etapas:
  1. Extracción de FastF1 (solo carreras disputadas que faltan)  -> data/raw/*_{año}.parquet
  2. Limpieza de vueltas                                          -> data/processed/laps_clean_{año}.parquet
  3. Carga en DuckDB                                              -> data/f1.duckdb
  4. Histórico de resultados y clasificaciones (Jolpica)          -> data/raw/history_*.parquet
  5. Variables y predicciones de podio "en vivo"                  -> data/processed/predicciones_podio.csv
  6. Modelo en estrella para Power BI                             -> data/processed/powerbi/
  7. Dashboard HTML                                               -> reports/dashboard.html

Es idempotente: si no hay carreras nuevas, vuelve a generar lo mismo. Si una etapa falla, el pipeline se detiene
con código de error distinto de 0 (para que GitHub Actions marque la ejecución como fallida).

Uso (desde la raíz del proyecto):
    python src/pipeline.py                      # año en curso
    python src/pipeline.py --year 2026
    python src/pipeline.py --year 2026 --completo       # vuelve a descargar toda la temporada
    python src/pipeline.py --year 2026 --sin-descarga   # solo reprocesa lo que ya hay en disco
"""

import argparse
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RAW = os.path.join('data', 'raw')


def etapa(numero, nombre):
    print(f'\n=== Etapa {numero}: {nombre} ===', flush=True)


def ejecutar(year, completo=False, sin_descarga=False):
    """Ejecuta el pipeline y devuelve un diccionario con el resumen (nº de carreras nuevas, etc.)."""
    # Los imports van aquí dentro para que `--help` y los tests de este módulo no carguen FastF1 ni scikit-learn.
    import clean
    import dashboard
    import extract
    import extract_history
    import load
    import model
    import powerbi_export

    inicio = time.time()
    resumen = {'year': year, 'carreras_nuevas': []}

    etapa(1, f'Extracción FastF1 {year}')
    if sin_descarga:
        print('Omitida (--sin-descarga).')
    else:
        resumen['carreras_nuevas'] = extract.descargar_temporada(year, solo_nuevas=not completo)
        print(f'Carreras nuevas: {resumen["carreras_nuevas"] or "ninguna"}')

    hay_vueltas = os.path.exists(os.path.join(RAW, f'laps_{year}.parquet'))

    etapa(2, 'Limpieza')
    if hay_vueltas:
        clean.limpiar_temporada(year)
    else:
        print(f'No hay vueltas de {year} todavía (¿ha empezado la temporada?): se omite.')

    etapa(3, 'Carga en DuckDB')
    if hay_vueltas:
        load.cargar_en_duckdb(year)
    else:
        print('Omitida.')

    etapa(4, 'Histórico de resultados (Jolpica)')
    if sin_descarga:
        print('Omitida (--sin-descarga).')
    else:
        extract_history.actualizar_historico(year)

    etapa(5, 'Predicciones en vivo')
    n = model.actualizar_predicciones()
    print(f'Carreras en vivo predichas: {n}')
    resumen['carreras_predichas'] = n

    etapa(6, 'Modelo en estrella para Power BI')
    tablas = powerbi_export.construir_modelo()
    errores = powerbi_export.validar(tablas)
    if errores:
        raise RuntimeError('Errores de integridad en el modelo en estrella:\n' + '\n'.join(errores))
    powerbi_export.exportar(tablas)
    print(f'{len(tablas)} tablas exportadas, integridad OK.')

    etapa(7, 'Dashboard HTML')
    dashboard.generar()

    resumen['segundos'] = round(time.time() - inicio)
    print(f'\nPipeline terminado en {resumen["segundos"]} s. Resumen: {resumen}')
    return resumen


def main(argv=None):
    parser = argparse.ArgumentParser(description='Actualiza los datos, modelos e informes del proyecto para un año.')
    parser.add_argument('--year', type=int, default=date.today().year, help='temporada (por defecto, el año en curso)')
    parser.add_argument('--completo', action='store_true', help='vuelve a descargar todas las carreras del año')
    parser.add_argument('--sin-descarga', action='store_true', help='no descarga nada: reprocesa los datos que ya hay')
    args = parser.parse_args(argv)
    ejecutar(args.year, completo=args.completo, sin_descarga=args.sin_descarga)


if __name__ == '__main__':
    main()
