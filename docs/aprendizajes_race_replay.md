# Aprendizajes de f1-race-replay

Repositorio: https://github.com/IAmTomShaw/f1-race-replay (Tom Shaw, licencia MIT)

## Cómo funciona (flujo de datos)

1. **Telemetría por piloto:** para cada vuelta, `lap.get_telemetry()` da posición (X, Y), distancia, velocidad, marcha, acelerador, freno y DRS.
2. **Línea de tiempo común:** cada piloto tiene mediciones en instantes distintos, así que las reescala con `np.interp` a un reloj común de 25 fotogramas por segundo.
3. **Clasificación en cada instante:** ordena a los pilotos por (vuelta, distancia recorrida). El que más distancia lleva es el líder.
4. **Caché:** guarda el resultado en un archivo `.pkl` para que la segunda vez cargue al instante.

✏️ Por qué hace falta la línea de tiempo común:

## Técnicas que voy a reutilizar

- **`np.interp`** para alinear datos medidos en momentos distintos.
  ✏️ Dónde lo usaré en mi proyecto:
- **`multiprocessing.Pool`** para procesar los 20 pilotos a la vez.
  ✏️ Qué parte de mi proyecto podría acelerar:
- **Caché de resultados calculados** para no repetir trabajo pesado.
  ✏️ Dónde la aplicaría:

## Datos que usa y yo no tenía

- `session.weather_data`: meteorología
- `session.track_status`: periodos de safety car, VSC y banderas
- `session.race_control_messages`: mensajes de dirección de carrera
- `PitInTime` / `PitOutTime`: tiempo en el pit lane

## Dudas

✏️ Lo que no he entendido (para preguntarlo):