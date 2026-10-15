"""
summary.py
Genera un resumen de ~200 palabras de la última carrera disputada con la API de Anthropic y lo guarda en
reports/summaries/ (un archivo Markdown por carrera).

PRINCIPIO: el modelo solo puede usar los datos que le pasamos. Por eso el script (1) construye un paquete de
datos a partir de las tablas del proyecto, (2) se lo entrega al modelo en el mensaje y (3) le ordena en el
prompt de sistema que no añada nada que no esté ahí. Esto reduce el riesgo de que "invente" hechos
(adelantamientos, incidentes, el tiempo...) que nuestros datos no contienen.

Configuración (variables de entorno, NUNCA en el código):
    ANTHROPIC_API_KEY   clave de la API (en GitHub: Settings -> Secrets and variables -> Actions -> New secret)
    ANTHROPIC_MODEL     modelo a usar (opcional; por defecto claude-sonnet-5-5)

Uso (desde la raíz del proyecto):
    python src/summary.py                 # última carrera del año en curso
    python src/summary.py --year 2026
    python src/summary.py --dry-run       # muestra el prompt y los datos sin llamar a la API (no gasta nada)
    python src/summary.py --forzar        # regenera aunque el resumen ya exista
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone

import pandas as pd

STAR = os.path.join('data', 'processed', 'powerbi')
SALIDA = os.path.join('reports', 'summaries')
MODELO_POR_DEFECTO = 'claude-sonnet-5-5'
PALABRAS_OBJETIVO = 200

SISTEMA = f"""Eres un redactor de crónicas de Fórmula 1 para un proyecto de análisis de datos.

Escribe en español un resumen de unas {PALABRAS_OBJETIVO} palabras de la carrera descrita en los datos JSON del mensaje del usuario.

Reglas estrictas:
- Usa EXCLUSIVAMENTE los datos del JSON. No añadas información externa (adelantamientos, incidentes, estrategias concretas,
  declaraciones, el tiempo, récords...) que no aparezca en esos datos. Si un dato no está, no lo menciones ni lo supongas.
- No inventes cifras: cada número que escribas debe salir de los datos. Los puntos son solo de carrera (sin sprints).
- Menciona: el podio, algún dato llamativo del resultado (por ejemplo posiciones ganadas desde la parrilla o abandonos),
  cómo queda el campeonato y qué dijo el modelo de predicción de podios frente a lo que ocurrió.
- Si en los datos aparece lluvia, o información de compuestos de neumáticos, puedes comentarlo; si no, no hables de ello.
- Tono claro y directo, sin exageraciones. Un solo bloque de texto de 1 o 2 párrafos, sin títulos ni listas ni emojis."""


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def leer(nombre):
    return pd.read_csv(os.path.join(STAR, f'{nombre}.csv'), encoding='utf-8-sig')


def ultima_carrera(year):
    """Devuelve el CarreraId de la última carrera con resultados del año, o None si no hay ninguna."""
    r = leer('fact_resultados')
    ids = r.loc[r['CarreraId'] // 100 == year, 'CarreraId']
    return int(ids.max()) if len(ids) else None


def paquete_de_datos(carrera_id):
    """Reúne, en un diccionario, todo lo que el modelo puede usar para escribir sobre una carrera."""
    carrera = leer('dim_carrera').set_index('CarreraId').loc[carrera_id]
    pilotos = leer('dim_piloto').set_index('PilotoId')['Piloto']
    equipos = leer('dim_equipo').set_index('EquipoId')['Equipo']

    res = leer('fact_resultados')
    anio = carrera_id // 100
    esta = res[res['CarreraId'] == carrera_id].sort_values('Posicion').copy()
    esta['Piloto'] = esta['PilotoId'].map(pilotos)
    esta['Equipo'] = esta['EquipoId'].map(equipos)

    # Clasificación del campeonato tras esta carrera (solo puntos de carrera)
    hasta = res[(res['CarreraId'] // 100 == anio) & (res['CarreraId'] <= carrera_id)]
    pts_pilotos = hasta.groupby('PilotoId')['Puntos'].sum().sort_values(ascending=False).head(5)
    pts_equipos = hasta.groupby('EquipoId')['Puntos'].sum().sort_values(ascending=False).head(3)

    datos = {
        'carrera': {
            'gran_premio': carrera['GranPremio'],
            'temporada': int(anio),
            'ronda': int(carrera['Ronda']),
            'fecha': carrera['Fecha'],
            'carreras_disputadas_en_la_temporada': int(hasta['CarreraId'].nunique()),
        },
        'resultado_top10': [
            {
                'posicion': int(f.Posicion),
                'piloto': f.Piloto,
                'equipo': f.Equipo,
                'salio': int(f.ParrillaAj),
                'puntos': float(f.Puntos),
                'estado': f.Estado,
            }
            for f in esta.head(10).itertuples()
        ],
        'abandonos_o_no_clasificados': [
            {'piloto': f.Piloto, 'equipo': f.Equipo, 'estado': f.Estado}
            for f in esta[esta['Abandono'] == 1].itertuples()
        ],
        'clasificacion_pilotos_tras_la_carrera': [
            {'piloto': pilotos[i], 'puntos': float(p)} for i, p in pts_pilotos.items()
        ],
        'clasificacion_constructores_tras_la_carrera': [
            {'equipo': equipos[i], 'puntos': float(p)} for i, p in pts_equipos.items()
        ],
    }

    # Mayores remontadas
    esta['Ganadas'] = esta['PosicionesGanadas']
    remontada = esta.sort_values('Ganadas', ascending=False).iloc[0]
    if remontada['Ganadas'] > 0:
        datos['mayor_remontada'] = {
            'piloto': remontada['Piloto'],
            'salio': int(remontada['ParrillaAj']),
            'acabo': int(remontada['Posicion']),
        }

    # Predicción del modelo (si existe para esta carrera)
    pred = leer('fact_predicciones')
    pred = pred[pred['CarreraId'] == carrera_id].sort_values('RankProba')
    if len(pred):
        pred = pred.assign(Piloto=pred['PilotoId'].map(pilotos))
        datos['prediccion_del_modelo'] = {
            'descripcion': 'Los 3 pilotos con más probabilidad de podio según el modelo (calculada antes de la carrera). '
            'Las probabilidades normalizadas suman 3 por carrera.',
            'top3_predicho': [
                {
                    'piloto': f.Piloto,
                    'probabilidad_normalizada': float(f.ProbaPodioNorm),
                    'acabo_en': int(f.PosicionReal),
                }
                for f in pred.head(3).itertuples()
            ],
            'podios_acertados_de_3': int(pred['Acierto'].sum()),
            'podio_real_no_predicho': [
                f.Piloto for f in pred[(pred['PodioReal'] == 1) & (pred['PredPodio'] == 0)].itertuples()
            ],
        }

    # Neumáticos y lluvia, solo si hay vueltas limpias de esa carrera
    vueltas = leer('fact_vueltas')
    v = vueltas[vueltas['CarreraId'] == carrera_id]
    if len(v):
        datos['lluvia'] = {'porcentaje_de_vueltas_limpias_con_lluvia': round(float(v['Lluvia'].mean() * 100), 1)}
        estrategias = []
        for pid in esta.head(5)['PilotoId']:
            s = (
                v[(v['PilotoId'] == pid) & (v['Compuesto'] != 'DESCONOCIDO')]
                .dropna(subset=['Stint'])
                .sort_values(['Stint', 'Vuelta'])
            )
            orden = list(dict.fromkeys(zip(s['Stint'], s['Compuesto'])))
            if orden:
                estrategias.append({'piloto': pilotos[pid], 'compuestos_en_orden': [c for _, c in orden]})
        if estrategias:
            datos['neumaticos_top5'] = {
                'descripcion': 'Compuestos usados por cada piloto, en orden (según las vueltas limpias disponibles; '
                'no se conocen las vueltas de cada tanda).',
                'pilotos': estrategias,
            }
    return datos


# ---------------------------------------------------------------------------
# Llamada a la API
# ---------------------------------------------------------------------------


def mensaje_usuario(datos):
    return 'Datos de la carrera (JSON). Escribe el resumen usando solo estos datos:\n\n' + json.dumps(
        datos, ensure_ascii=False, indent=1
    )


def generar_resumen(cliente, modelo, datos):
    """Llama a la API y devuelve el texto del resumen. Lanza RuntimeError si la respuesta no es utilizable."""
    respuesta = cliente.messages.create(
        model=modelo,
        # El razonamiento adaptativo del modelo cuenta dentro de max_tokens: se deja un margen amplio.
        max_tokens=4000,
        system=SISTEMA,
        messages=[{'role': 'user', 'content': mensaje_usuario(datos)}],
        output_config={'effort': 'low'},  # tarea sencilla: no hace falta razonar a fondo
    )
    if respuesta.stop_reason == 'refusal':
        raise RuntimeError('El modelo ha rechazado la petición (stop_reason = refusal).')
    if respuesta.stop_reason == 'max_tokens':
        raise RuntimeError('La respuesta se cortó por max_tokens: aumenta el límite.')
    texto = '\n\n'.join(b.text for b in respuesta.content if b.type == 'text').strip()
    if not texto:
        raise RuntimeError('La respuesta no contiene texto.')
    return texto


def contar_palabras(texto):
    return len(re.findall(r'\w+', texto, flags=re.UNICODE))


def nombre_archivo(datos):
    c = datos['carrera']
    slug = unicodedata.normalize('NFKD', c['gran_premio']).encode('ascii', 'ignore').decode().lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug).strip('_')
    return f"{c['temporada']}_R{c['ronda']:02d}_{slug}.md"


def guardar(texto, datos, modelo, carpeta=SALIDA):
    os.makedirs(carpeta, exist_ok=True)
    c = datos['carrera']
    ruta = os.path.join(carpeta, nombre_archivo(datos))
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(
            f"---\ncarrera: {c['gran_premio']} {c['temporada']}\nfecha: {c['fecha']}\nmodelo: {modelo}\n"
            f"generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"palabras: {contar_palabras(texto)}\n---\n\n"
            f"> Resumen generado por un modelo de lenguaje únicamente a partir de los datos del proyecto "
            f"(resultados, predicciones del modelo de podios y vueltas limpias). Puede contener errores de redacción.\n\n"
            f"{texto}\n"
        )
    return ruta


def main(argv=None):
    parser = argparse.ArgumentParser(description='Resumen de la última carrera con la API de Anthropic.')
    parser.add_argument('--year', type=int, default=date.today().year, help='temporada (por defecto, el año en curso)')
    parser.add_argument('--dry-run', action='store_true', help='muestra el prompt y los datos sin llamar a la API')
    parser.add_argument('--forzar', action='store_true', help='regenera el resumen aunque ya exista')
    args = parser.parse_args(argv)

    carrera_id = ultima_carrera(args.year)
    if carrera_id is None:
        print(f'No hay carreras disputadas en {args.year}: no hay nada que resumir.')
        return 0
    datos = paquete_de_datos(carrera_id)
    ruta = os.path.join(SALIDA, nombre_archivo(datos))
    modelo = os.environ.get('ANTHROPIC_MODEL') or MODELO_POR_DEFECTO  # vacío o ausente -> valor por defecto

    if args.dry_run:
        print(f'Modelo: {modelo}\n\n--- SISTEMA ---\n{SISTEMA}\n\n--- USUARIO ---\n{mensaje_usuario(datos)}')
        return 0
    if os.path.exists(ruta) and not args.forzar:
        print(f'Ya existe {ruta}: no se vuelve a llamar a la API (usa --forzar para regenerarlo).')
        return 0
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print(
            'AVISO: no hay ANTHROPIC_API_KEY en el entorno; se omite el resumen. '
            '(En GitHub: Settings -> Secrets and variables -> Actions -> New repository secret.)'
        )
        return 0

    import anthropic  # import local: el resto del proyecto no necesita el SDK

    cliente = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno
    try:
        texto = generar_resumen(cliente, modelo, datos)
    except anthropic.RateLimitError:
        print('ERROR: límite de peticiones de la API (429). Vuelve a intentarlo más tarde.')
        return 1
    except anthropic.APIStatusError as e:
        print(f'ERROR de la API (HTTP {e.status_code}): {e.message}')
        return 1
    except anthropic.APIConnectionError as e:
        print(f'ERROR de conexión con la API: {e}')
        return 1
    except RuntimeError as e:
        print(f'ERROR: {e}')
        return 1

    palabras = contar_palabras(texto)
    if not 130 <= palabras <= 270:
        print(f'AVISO: el resumen tiene {palabras} palabras (objetivo: {PALABRAS_OBJETIVO}).')
    print(f'Guardado {guardar(texto, datos, modelo)} ({palabras} palabras, modelo {modelo})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
