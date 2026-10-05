# 🏎️ F1 Strategy Analytics

Proyecto de análisis de datos sobre estrategia en Fórmula 1: telemetría, degradación de neumáticos, predicción de resultados y dashboard interactivo.

## Pregunta principal

¿Qué separa a los pilotos y equipos que ganan, y qué estrategia habría sido la óptima en cada carrera?

## Objetivos

- **Telemetría:** comparar pilotos vuelta a vuelta y ver dónde se gana el tiempo.
- **Estrategia:** modelar la degradación de neumáticos y estimar la parada óptima.
- **Predicción:** predecir qué pilotos acabarán en el podio con modelos de clasificación.
- **Dashboard:** presentar los resultados en Power BI.
- **Automatización:** actualizar los datos tras cada Gran Premio con GitHub Actions.

## Herramientas

Python (pandas, FastF1, DuckDB, scikit-learn) · Jupyter · VS Code · Git y GitHub · Power BI · GitHub Actions

## Estructura

```
├── data/          # datos (raw no se sube; processed para Power BI)
├── notebooks/     # análisis exploratorio
├── src/           # código reutilizable
├── sql/           # consultas
├── tests/         # tests
├── powerbi/       # dashboard
└── reports/       # gráficos y resúmenes
```

## Cómo ejecutarlo

```bash
git clone https://github.com/wewesito/f1-strategy-analytics.git
cd f1-strategy-analytics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Estado

🚧 En desarrollo: fase 1, obtención de datos.

## Autor

Álvaro Ruiz
