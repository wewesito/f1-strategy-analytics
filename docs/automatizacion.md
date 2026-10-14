# Automatización: pipeline semanal, tests y resúmenes

Cada **lunes a las 8:00 UTC** (y cuando lo lances a mano) GitHub Actions ejecuta `.github/workflows/update.yml`:

1. Instala las dependencias (`requirements-ci.txt`) y restaura la caché de FastF1 y de `data/raw/`.
2. Ejecuta los **tests** (`pytest`).
3. Ejecuta el **pipeline** del año en curso (`python src/pipeline.py --year AAAA`): descarga solo las carreras nuevas, limpia, carga en DuckDB, actualiza el histórico y las predicciones, regenera el modelo en estrella de Power BI y el dashboard.
4. Vuelve a ejecutar los **tests** con los datos nuevos. Si fallan, no se hace commit.
5. Genera el **resumen** de la última carrera con la API de Anthropic (`src/summary.py`), si existe la clave.
6. Hace **commit automático** de `data/processed/` y `reports/` (nunca de `data/raw/`, `cache/`, `*.duckdb` ni claves).

## Cómo crear el secret `ANTHROPIC_API_KEY` en GitHub

Un *secret* es un valor cifrado que solo ven los workflows: no aparece en el código, en los logs ni en los *forks*. **No pegues nunca la clave en un archivo del repositorio.**

1. Consigue una clave en [console.anthropic.com](https://console.anthropic.com) → **API keys** → **Create key**. Cópiala (solo se muestra una vez). Conviene crear una clave **solo para este proyecto** y ponerle un límite de gasto.
2. En GitHub, abre el repositorio → **Settings** → **Secrets and variables** → **Actions**.
3. Pestaña **Secrets** → **New repository secret**.
   - *Name:* `ANTHROPIC_API_KEY` (exactamente así)
   - *Secret:* pega la clave
   - **Add secret**
4. (Opcional) Para cambiar de modelo sin tocar el código: pestaña **Variables** → **New repository variable** → *Name* `ANTHROPIC_MODEL`, *Value* el id del modelo. Si no existe, se usa `claude-sonnet-5-5`.

Si el secret no existe, el paso del resumen avisa y termina sin error: el resto del pipeline funciona igual.

Si una clave se llega a publicar por error, **revócala** en la consola de Anthropic y crea otra; borrar el commit no basta porque queda en el historial.

## Cómo lanzarlo a mano

Pestaña **Actions** → **Actualización semanal** → **Run workflow**. Puedes indicar un año (vacío = año en curso).

La primera ejecución descarga toda la temporada y puede tardar bastante; las siguientes solo las carreras nuevas gracias a la caché.

## Comandos en local

```bash
source .venv/bin/activate
python src/pipeline.py --year 2026                # pipeline completo, solo carreras nuevas
python src/pipeline.py --year 2026 --sin-descarga # reprocesa lo que ya hay en disco
python src/pipeline.py --year 2026 --completo     # vuelve a descargar toda la temporada
python -m pytest -q                               # tests
export ANTHROPIC_API_KEY="..."                    # solo en tu terminal, nunca en un archivo
python src/summary.py --dry-run                   # ver el prompt sin llamar a la API
python src/summary.py                             # genera el resumen en reports/summaries/
```

## Limitaciones conocidas

- Los datos de FastF1 de una carrera pueden tardar horas en estar completos; el pipeline espera 3 horas tras la salida y, si una carrera falla, la reintenta en la siguiente ejecución.
- El modelo de podios no se reentrena: está entrenado con 2018-2025 y solo predice las carreras nuevas de 2026.
- Cada ejecución modifica `data/processed/laps_clean_AAAA.parquet` (~2 MB), así que el repositorio crecerá algunos MB al año.
- Los resúmenes los redacta un modelo de lenguaje a partir de los datos que se le entregan; se revisan por si hay errores de redacción, pero no se verifican automáticamente.
