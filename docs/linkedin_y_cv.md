# Borrador de post de LinkedIn y línea para el CV

Son borradores para que los adaptes con tu voz. Todas las cifras salen del proyecto (ver el README). Antes de publicar: pon el enlace al repositorio, sube el GIF `reports/figures/dashboard.gif` como imagen del post y comprueba que el repositorio es público.

---

## Post de LinkedIn

**Construí un modelo para predecir los podios de la F1. Y descubrí que no gana a la regla más simple. 🏎️**

Durante las últimas semanas he montado, de principio a fin, un proyecto de análisis de datos sobre estrategia en Fórmula 1: descarga de datos, telemetría, degradación de neumáticos, un modelo de predicción y un dashboard que se actualiza solo cada lunes.

Lo que más me ha enseñado fue la parte menos vistosa:

🔹 Mi modelo (Gradient Boosting) ordena mejor a los pilotos que la regla «los 3 primeros de la parrilla hacen podio»: AUC de 0,951 frente a 0,930 en 2025.
🔹 Pero, en las 41 carreras de 2025 y 2026, elige exactamente los mismos tres pilotos que esa regla. Acierta 54 de 72 podios en 2025, lo mismo que la regla.
🔹 La posición de salida lo explica casi todo. Lo que el modelo no ve (adelantamientos, estrategia, safety cars, abandonos) es justo lo que decide quién sube de la 4ª o 5ª posición.

Otras cosas que aprendí por el camino:
✅ El *data leakage* se esconde: una columna con los puntos de la propia carrera lleva el AUC a 1,000, pero las fugas sutiles apenas se notan en las métricas. Por eso valido las variables con tests (si alteras una carrera, las variables de esa carrera y las anteriores no pueden cambiar).
✅ Compararme con un modelo trivial desde el principio me ahorró vender un resultado inflado.
✅ Contrastar con el cronómetro oficial: en Mónaco la suma de tramos de mi telemetría salía con el signo contrario al tiempo real. Lo detecté, lo corregí documentando el supuesto y lo dejé explicado en el README.

🛠️ Stack: Python, FastF1, DuckDB, scikit-learn, Plotly, Power BI (modelo en estrella + medidas DAX), pytest y GitHub Actions.

El código, el dashboard interactivo y una guía para montarlo en Power BI están en el repositorio: [ENLACE]

Si trabajas con datos deportivos, me encantaría saber qué variables añadirías para predecir mejor a los pilotos que salen entre la 4ª y la 6ª posición.

#DataAnalytics #Python #MachineLearning #Formula1 #DataScience #PowerBI

---

### Notas sobre el post

- **El gancho es el resultado negativo, a propósito.** Un modelo que «funciona al 75 %» sin compararlo con una regla trivial es un resultado engañoso; contar que no gana demuestra criterio, que es lo que busca un reclutador.
- **Ajusta las frases a lo que hiciste tú.** Es un borrador redactado sobre el proyecto completo: cuenta con tus palabras lo que de verdad decidiste y entendiste (en una entrevista te preguntarán por ello), y si algo lo hiciste con ayuda de un asistente de IA, dilo con naturalidad.
- Si prefieres un tono más corto, quédate con el gancho, los tres puntos de 🔹 y el enlace.
- No digas que el dashboard «predice el campeón» ni que el modelo «acierta el 75 %» sin la comparación: el propio proyecto muestra que esa cifra la consigue una regla trivial.
- Puedes añadir una captura de la sección de Predicciones del dashboard (`reports/figures/dashboard_prediccion.png`) en un segundo post.

---

## Línea para el CV

Elige la que mejor encaje con el tamaño de tu CV.

**Una línea (castellano):**
> **F1 Strategy Analytics** · Pipeline de datos de F1 (FastF1, Jolpica, DuckDB) con modelo de predicción de podios (AUC 0,951 en test), dashboard en Power BI/Plotly y actualización semanal con GitHub Actions y 43 tests. — [github.com/wewesito/f1-strategy-analytics](https://github.com/wewesito/f1-strategy-analytics)

**One line (English):**
> **F1 Strategy Analytics** · End-to-end F1 data pipeline (FastF1, Jolpica, DuckDB) with a podium-prediction model (0.951 test AUC, benchmarked against a grid-position baseline), a Power BI/Plotly dashboard and a weekly GitHub Actions refresh backed by 43 tests. — github.com/wewesito/f1-strategy-analytics

**Versión con viñetas (si tienes espacio):**
- Construí un pipeline incremental en Python (FastF1, Jolpica, DuckDB) con 43 tests de calidad de datos y de ausencia de *data leakage*, actualizado cada semana con GitHub Actions.
- Modelé la degradación de neumáticos y simulé estrategias para encontrar la óptima en 3 Grandes Premios; comparé telemetría de clasificación tramo a tramo.
- Desarrollé un modelo de predicción de podios con validación temporal (AUC 0,951 en test) y lo evalué frente a una regla base, mostrando que ordena mejor pero elige el mismo podio.
- Diseñé un modelo en estrella para Power BI (medidas DAX, 4 páginas) y un dashboard HTML interactivo con Plotly.

### Preguntas que te harán en una entrevista sobre este proyecto

1. «Tu modelo no mejora la regla simple, ¿por qué es útil entonces?» (Ordena mejor al resto de la parrilla; el valor está en las probabilidades y en saber qué información falta.)
2. «¿Cómo evitaste el *data leakage*?» (`shift(1)` por grupo, división temporal, preprocesado dentro de un `Pipeline`, prueba de invarianza.)
3. «¿Qué cambiarías con más tiempo?» (Variables de carrera: estrategia, safety car por circuito, ritmo en libres; calibrar probabilidades; reentrenar cada semana.)
