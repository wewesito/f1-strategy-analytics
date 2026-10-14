# Guía de Power BI para F1 Strategy Analytics

Esta guía te lleva desde los archivos del proyecto hasta un informe de 4 páginas en **Power BI web** (app.powerbi.com). Los menús de Power BI cambian con frecuencia y dependen de la licencia de tu cuenta de la universidad, así que si algún botón no aparece donde indico, busca su nombre en el buscador de la parte superior o consúltalo conmigo.

Orden de lectura: **1.** Qué vas a cargar · **2.** Carga · **3.** Relaciones · **4.** Medidas DAX · **5.** Las 4 páginas · **6.** Equivalencias con Tableau Public.

---

## 1. Qué vas a cargar

La carpeta `data/processed/powerbi/` contiene un **modelo en estrella** (5 dimensiones y 6 tablas de hechos). Su explicación completa, con el diagrama de relaciones y el diccionario de columnas, está en `data/processed/powerbi/README.md`. Léelo antes de seguir.

Hay dos formas de entregarle los datos a Power BI web:

| Opción | Archivos | Cuándo usarla |
|---|---|---|
| **A. Excel (recomendada)** | `modelo_f1.xlsx`, con las 11 tablas ya definidas como *Tablas de Excel* | Es lo más simple: un solo archivo crea un modelo con todas las tablas. Funciona con cualquier licencia. |
| **B. CSV desde GitHub (flujo de datos)** | los 11 `.csv`, leídos por URL | Solo si tu licencia permite crear *flujos de datos* (dataflows) y quieres que se actualicen al hacer `git push`. |

Si todo va bien, usa la A. Si tu cuenta no te deja importar un Excel, pasa a la B.

---

## 2. Carga de los datos

### Opción A · Excel

1. Entra en **app.powerbi.com** con tu cuenta de la universidad. Trabaja en **Mi área de trabajo** (*My workspace*).
2. Menú izquierdo → **Crear** (*Create*) → **Obtener datos** (*Get data*) → **Archivos** (*Files*) → **Archivo local** (*Local file*), y elige `data/processed/powerbi/modelo_f1.xlsx`.
3. Cuando pregunte, elige **Importar** (*Import*) y **no** "Cargar" (*Upload*). Con *Importar*, Power BI lee las tablas y crea un **modelo semántico** (*semantic model*); con *Cargar* solo guarda el Excel como un documento.
4. En Mi área de trabajo aparecerá `modelo_f1` como modelo semántico. Ábrelo: **⋯ → Abrir modelo de datos** (*Open data model*) o **Editar modelo de datos**. Aparece la **vista de modelo** con las 11 tablas.

**Comprobaciones tras cargar** (haz clic en una tabla y mira la lista de columnas):

- Las columnas `Fecha` de `dim_calendario` y `dim_carrera` deben tener tipo **Fecha**. En el Excel ya son fechas reales.
- Las columnas con sufijo `Id` pueden aparecer como texto (`PilotoId`, `EquipoId`) o número (`CarreraId`); ambas cosas son correctas. Lo que importa es que **la columna en la tabla de hechos y en la dimensión tengan el mismo tipo**.
- `GranPremio`, `Piloto`, etc. deben conservar las tildes y la ñ. Si aparecen caracteres raros, vuelve a generar el Excel con `python src/powerbi_export.py`.

### Opción B · CSV desde GitHub (flujo de datos)

El repositorio es público, así que cada CSV tiene una URL directa del tipo
`https://raw.githubusercontent.com/wewesito/f1-strategy-analytics/main/data/processed/powerbi/fact_resultados.csv`.

1. En tu área de trabajo → **Nuevo** → **Flujo de datos** (*Dataflow Gen1*) → **Definir nuevas tablas** → **Texto/CSV**.
2. Pega la URL de una tabla. En el editor de Power Query abre **Configuración de origen** y fija la **configuración regional: Inglés (Estados Unidos)** (los decimales llevan punto; con configuración española se leerían como miles).
3. Repite con las 11 tablas, **guarda y actualiza**.
4. Crea un informe desde ese flujo de datos (**Crear → Obtener datos → Flujos de datos**).

> Si no ves la opción *Flujo de datos*, tu licencia no la incluye: usa la opción A.

---

## 3. Crear las relaciones (vista de modelo)

Si tras cargar el modelo Power BI ya ha detectado algunas relaciones por el nombre de la columna, **revísalas** una a una: debe ser **Muchos a uno (\*:1)** y **dirección del filtro: Única**.

Para crear una relación, arrastra la columna de la **tabla de hechos** sobre la columna de la **dimensión**, o usa **Administrar relaciones → Nueva**. En el cuadro que se abre:

| Desde (muchos) | Columna | Hacia (uno) | Columna | Activa |
|---|---|---|---|---|
| `dim_carrera` | `Fecha` | `dim_calendario` | `Fecha` | sí |
| `fact_resultados` | `CarreraId` | `dim_carrera` | `CarreraId` | sí |
| `fact_resultados` | `PilotoId` | `dim_piloto` | `PilotoId` | sí |
| `fact_resultados` | `EquipoId` | `dim_equipo` | `EquipoId` | sí |
| `fact_vueltas` | `CarreraId` / `PilotoId` / `EquipoId` | `dim_carrera` / `dim_piloto` / `dim_equipo` | las claves del mismo nombre | sí |
| `fact_vueltas` | `Compuesto` | `dim_compuesto` | `Compuesto` | sí |
| `fact_estrategias` | `CarreraId` / `PilotoId` / `EquipoId` | `dim_carrera` / `dim_piloto` / `dim_equipo` | las claves del mismo nombre | sí |
| `fact_degradacion` | `CarreraId` / `PilotoId` / `EquipoId` | las tres dimensiones | las claves del mismo nombre | sí |
| `fact_degradacion` | `Compuesto` | `dim_compuesto` | `Compuesto` | sí |
| `fact_telemetria_tramos` | `CarreraId` | `dim_carrera` | `CarreraId` | sí |
| `fact_telemetria_tramos` | `Piloto1Id` | `dim_piloto` | `PilotoId` | **sí** |
| `fact_telemetria_tramos` | `Piloto2Id` | `dim_piloto` | `PilotoId` | **no** (desmarca *Hacer activa esta relación*) |
| `fact_predicciones` | `CarreraId` / `PilotoId` / `EquipoId` | las tres dimensiones | las claves del mismo nombre | sí |

Son 21 relaciones. La de `Piloto2Id` es **inactiva** porque dos relaciones activas entre las mismas dos tablas son ambiguas; la usaremos con `USERELATIONSHIP` en una medida.

**Buenas prácticas del modelo** (hazlas ahora, se agradecen luego):

- Oculta las columnas de clave de los hechos (`CarreraId`, `PilotoId`, `EquipoId`, `Piloto1Id`, `Piloto2Id`): en los informes se usan las columnas de las dimensiones. Botón derecho → **Ocultar en la vista de informe**.
- En `dim_carrera`, ordena `Etiqueta` por `CarreraId`: columna `Etiqueta` → **Ordenar por columna** → `CarreraId`. Así los ejes salen en orden cronológico y no alfabético.
- En `dim_calendario`, ordena `NombreMes` por `Mes`.
- Opcional: marca `dim_calendario` como **tabla de fechas** (columna `Fecha`). No hace falta para las medidas de esta guía.

**Cómo comprobar que está bien:** crea una tabla en un informe con `dim_piloto[Piloto]` y `SUM` de `fact_resultados[Puntos]` filtrada por `dim_carrera[Anio] = 2024`. Verstappen debe sumar **399** y Norris **344** (puntos solo de carreras, sin *sprints*). Si todos los pilotos muestran el mismo total, falta una relación o está mal dirigida.

---

## 4. Medidas DAX (listas para copiar)

Una **medida** es un cálculo que se recalcula según los filtros activos (piloto, GP, año...). Se crea en la vista de informe o de modelo: selecciona la tabla → **Nueva medida** → pega el código en la barra de fórmulas.

Cada medida va en la tabla de hechos que usa. En la columna **Esperado** tienes el valor que debes obtener con el filtro indicado, calculado con pandas sobre los mismos datos: sirve para comprobar que tu modelo está bien conectado.

> **Convención:** si un nombre de medida lleva paréntesis, como `[Ritmo medio (s)]`, escríbelo tal cual al referenciarlo.

### 4.1 Resultados (tabla `fact_resultados`, 2018-2026)

```dax
Puntos = SUM(fact_resultados[Puntos])

Victorias = SUM(fact_resultados[Victoria])

Podios = SUM(fact_resultados[Podio])

Carreras = DISTINCTCOUNT(fact_resultados[CarreraId])

Abandonos = SUM(fact_resultados[Abandono])

% Abandonos = DIVIDE([Abandonos], COUNTROWS(fact_resultados))

Posición media = AVERAGE(fact_resultados[Posicion])

Posiciones ganadas medias = AVERAGE(fact_resultados[PosicionesGanadas])

% Podios = DIVIDE([Podios], COUNTROWS(fact_resultados))
```

`DIVIDE(a, b)` devuelve vacío si `b` es 0, en vez de un error.

**Puntos acumulados en la temporada** (para la curva de campeonato). Suma los puntos de todas las carreras de ese año hasta la carrera del eje:

```dax
Puntos acumulados =
VAR _anio  = MAX(dim_carrera[Anio])
VAR _fecha = MAX(dim_carrera[Fecha])
RETURN
    CALCULATE(
        [Puntos],
        FILTER(
            ALL(dim_carrera),
            dim_carrera[Anio] = _anio && dim_carrera[Fecha] <= _fecha
        )
    )
```

`ALL(dim_carrera)` quita el filtro de carrera (si no, solo vería la carrera de ese punto del eje). Guardar el año y la fecha en variables (`VAR`) *antes* del `CALCULATE` es lo que evita que se pierdan al quitar el filtro. Los filtros de piloto y equipo se mantienen.

| Medida | Filtro | Esperado |
|---|---|---|
| Puntos | Piloto = Max Verstappen, Anio = 2024 | **399** |
| Puntos | Equipo = McLaren, Anio = 2024 | **609** |
| Victorias / Podios | Anio = 2024 (sin más filtros) | **24 / 72** |
| Carreras | Anio = 2024 | **24** |
| Abandonos / % Abandonos | Anio = 2024 | **47 / 9,81 %** |
| Podios | Verstappen, 2024 | **14** |
| Posición media | Verstappen, 2024 | **3,625** |
| Puntos acumulados | Verstappen, 2024, última carrera (R24) | **399** |

### 4.2 Ritmo de carrera (tabla `fact_vueltas`, 2024 y 2026)

```dax
Ritmo medio (s) = AVERAGE(fact_vueltas[TiempoCorregidoSeg])

Mejor vuelta (s) = MIN(fact_vueltas[TiempoVueltaSeg])

Vueltas válidas = COUNTROWS(fact_vueltas)

Ritmo vs campo (s) =
VAR _propio = [Ritmo medio (s)]
VAR _campo =
    CALCULATE(
        [Ritmo medio (s)],
        REMOVEFILTERS(dim_piloto),
        REMOVEFILTERS(dim_equipo)
    )
RETURN _propio - _campo
```

`TiempoCorregidoSeg` es el tiempo por vuelta sin el efecto del combustible (100 kg y 0,03 s/kg; mismo supuesto que la Fase 3). `Ritmo vs campo` resta al ritmo del piloto o equipo seleccionado el ritmo medio de **todos** en esa carrera: un valor negativo significa "más rápido que la media". Se actualiza con cada carrera nueva de 2026 (pipeline semanal), así que filtra siempre por año. Compara siempre dentro de la carrera seleccionada: no mezcles circuitos en una misma media, porque Mónaco y Spa no son comparables.

| Medida | Filtro | Esperado |
|---|---|---|
| Ritmo medio (s) | Anio = 2024 | **87,404** |
| Ritmo medio (s) | Verstappen, Anio = 2024 | **86,668** |
| Ritmo medio (s) | GP de Italia | **83,341** |
| Mejor vuelta (s) | Anio = 2024 | **67,694** |

### 4.3 Estrategia y degradación (tablas `fact_estrategias` y `fact_degradacion`, solo 2024)

```dax
Paradas medias = AVERAGE(fact_estrategias[Paradas])

Pérdida vs óptima (s) = AVERAGE(fact_estrategias[VsOptimaSeg])

Degradación (s/vuelta) =
DIVIDE(
    SUMX(fact_degradacion, fact_degradacion[DegradacionSegVuelta] * fact_degradacion[Vueltas]),
    SUM(fact_degradacion[Vueltas])
)

Stints = COUNTROWS(fact_degradacion)
```

La degradación es la media **ponderada por vueltas**: un stint de 30 vueltas pesa más que uno de 8. `AVERAGE` ignora los vacíos, y hay una estrategia sin comparación (Stroll en Hungría, que usó blandos, ya excluidos del modelo).

| Medida | Filtro | Esperado |
|---|---|---|
| Paradas medias | toda la tabla | **1,833** |
| Pérdida vs óptima (s) | toda la tabla | **12,96** |
| Pérdida vs óptima (s) | Baréin / Hungría / Italia | **3,75 / 24,97 / 11,37** |
| Degradación (s/vuelta) | toda la tabla | **0,0514** |

### 4.4 Telemetría (tabla `fact_telemetria_tramos`, solo 2024)

```dax
Tiempo ganado por piloto 1 (s) = SUM(fact_telemetria_tramos[GanaP1Seg])

Tiempo ganado (telemetría cruda) (s) = SUM(fact_telemetria_tramos[GanaP1CrudoSeg])

Diferencia oficial de vuelta (s) = MAX(fact_telemetria_tramos[DifOficialSeg])

Ventaja acumulada P1 (s) =
VAR _orden = MAX(fact_telemetria_tramos[OrdenTramo])
RETURN
    CALCULATE(
        SUM(fact_telemetria_tramos[GanaP1Seg]),
        FILTER(
            ALLSELECTED(fact_telemetria_tramos[OrdenTramo]),
            fact_telemetria_tramos[OrdenTramo] <= _orden
        )
    )

Tramos del piloto como piloto 2 =
CALCULATE(
    COUNTROWS(fact_telemetria_tramos),
    USERELATIONSHIP(fact_telemetria_tramos[Piloto2Id], dim_piloto[PilotoId])
)
```

`GanaP1Seg` positivo = el primer piloto del duelo gana tiempo en ese tramo; negativo = lo pierde. **Ojo con el ajuste:** la telemetría cruda no suma el tiempo oficial (en Mónaco ni siquiera tiene el mismo signo), así que `GanaP1Seg` ya viene repartida para que la suma de los tramos sea la diferencia oficial (`DifOficialSeg`); el detalle está en `data/processed/powerbi/README.md`. `Diferencia oficial` usa `MAX` porque es un valor constante por duelo: solo tiene sentido con **un duelo seleccionado**. `Ventaja acumulada` es una suma acumulada tramo a tramo y, en el último tramo, coincide con la diferencia oficial. `USERELATIONSHIP` activa solo dentro de esa medida la relación inactiva `Piloto2Id → dim_piloto`.

Recuerda: el signo de cada duelo se refiere **al piloto 1 del duelo**. Por eso conviene filtrar con la columna `Duelo` (por ejemplo `NOR vs LEC`) y no solo con la dimensión de pilotos.

| Medida | Filtro | Esperado |
|---|---|---|
| Tiempo ganado por piloto 1 (s) | Duelo = `NOR vs LEC` (Monza) | **+0,134** |
| Tiempo ganado por piloto 1 (s) | Duelo = `VER vs NOR` (Suzuka) | **+0,292** |
| Tiempo ganado por piloto 1 (s) | Duelo = `LEC vs PIA` (Mónaco) | **+0,154** |
| Tiempo ganado (telemetría cruda) (s) | Monza / Suzuka / Mónaco | **+0,066 / +0,276 / −0,253** |

### 4.5 Predicciones (tabla `fact_predicciones`, 2025-2026)

```dax
Podios acertados = SUM(fact_predicciones[Acierto])

Podios predichos = SUM(fact_predicciones[PredPodio])

Podios reales = SUM(fact_predicciones[PodioReal])

% Acierto del modelo = DIVIDE([Podios acertados], [Podios predichos])

% Acierto trivial =
DIVIDE(
    CALCULATE(
        COUNTROWS(fact_predicciones),
        fact_predicciones[PredTrivial] = 1,
        fact_predicciones[PodioReal] = 1
    ),
    SUM(fact_predicciones[PredTrivial])
)

Mejora vs trivial (pp) = ([% Acierto del modelo] - [% Acierto trivial]) * 100

Podios sorpresa =
CALCULATE(
    COUNTROWS(fact_predicciones),
    fact_predicciones[PodioReal] = 1,
    fact_predicciones[PredPodio] = 0
)

Probabilidad de podio = AVERAGE(fact_predicciones[ProbaPodioNorm])
```

El modelo marca como podio a los 3 pilotos con más probabilidad de cada carrera: hay 3 elegidos y 3 podios reales, así que precisión y recall coinciden y por eso `% Acierto` es un único número. `Podios sorpresa` cuenta los podios reales que el modelo no había marcado. `Mejora vs trivial` vale **0** en estos datos (el modelo elige los mismos 3 pilotos que "los 3 primeros de la parrilla"); es un resultado honesto del proyecto y conviene mostrarlo en el dashboard.

| Medida | Filtro | Esperado |
|---|---|---|
| Podios acertados / predichos | Conjunto = Test 2025 | **54 / 72** |
| % Acierto del modelo | Test 2025 | **75,0 %** |
| % Acierto del modelo | En vivo 2026 | **62,7 %** (32 de 51) |
| % Acierto trivial | Test 2025 / En vivo 2026 | **75,0 % / 62,7 %** |
| Podios sorpresa | Test 2025 / En vivo 2026 | **18 / 19** |

### 4.6 Formato recomendado

Selecciona la medida → pestaña **Herramientas de medida**: `% ...` en formato **Porcentaje** (1 decimal); los segundos con 3 decimales (2 para `Pérdida vs óptima`); `Puntos`, `Victorias`, `Podios` y recuentos como **Número entero**.

---

## 5. Las 4 páginas del informe

Cada página responde a **una pregunta**. Usa el mismo estilo en las cuatro: fondo oscuro o blanco liso, un solo color de acento (rojo F1 `#E10600`), títulos que digan la conclusión y no el nombre del gráfico, y los **colores Pirelli** de `dim_compuesto[ColorHex]` en todo lo que sea neumáticos.

> **Alcance temporal:** resultados cubren 2018-2026, predicciones 2025-2026 y vueltas 2024 y 2026; estrategia, degradación y telemetría son solo de 2024. Pon un filtro de página `dim_carrera[Anio] = 2024` en las páginas 2 y 3, y avisa con un texto cuando una página sea de un solo año.

### Página 1 · Resumen de temporada
*¿Quién ganó la temporada y cómo se fue construyendo?* · datos: `fact_resultados` (2018-2026)

| Zona | Elemento | Campos |
|---|---|---|
| Arriba izquierda | **Segmentación (slicer)** de año, selección única | `dim_carrera[Anio]` |
| Fila superior | **4 tarjetas**: Carreras, Victorias, Podios, % Abandonos | medidas |
| Izquierda | **Barras horizontales**: clasificación de pilotos (top 10) | eje `dim_piloto[Piloto]`, valor `[Puntos]`, filtro *Top N = 10* por `[Puntos]` |
| Derecha | **Barras horizontales**: clasificación de constructores | eje `dim_equipo[Equipo]`, valor `[Puntos]` |
| Centro, ancho | **Líneas**: evolución del campeonato | eje `dim_carrera[Etiqueta]`, valor `[Puntos acumulados]`, leyenda `dim_piloto[Piloto]` con Top N = 5 |
| Abajo | **Matriz**: posición por carrera | filas `dim_piloto[Piloto]`, columnas `dim_carrera[Ronda]`, valores `[Posición media]` con formato condicional (verde = mejor) |

Por qué estos gráficos: las barras ordenadas comparan totales; la línea acumulada enseña *cuándo* se decidió el campeonato (un cruce de líneas es la historia); la matriz de calor detecta rachas de resultados de un vistazo.

### Página 2 · Telemetría
*¿Dónde se gana el tiempo entre dos pilotos?* · datos: `fact_telemetria_tramos` (2024: Mónaco, Monza y Suzuka, clasificación)

| Zona | Elemento | Campos |
|---|---|---|
| Arriba izquierda | **Segmentación** de duelo | `fact_telemetria_tramos[Duelo]` |
| Arriba | **2 tarjetas**: diferencia oficial de vuelta y nº de tramos | `[Diferencia oficial de vuelta (s)]`, `COUNTROWS` |
| Centro izquierda | **Columnas**: tiempo ganado en cada tramo | eje `[Tramo]` ordenado por `OrdenTramo`, valor `[Tiempo ganado por piloto 1 (s)]`; formato condicional (azul positivo, rojo negativo) |
| Centro derecha | **Líneas**: ventaja acumulada a lo largo de la vuelta | eje `[OrdenTramo]`, valor `[Ventaja acumulada P1 (s)]` |
| Abajo | **Tabla** de tramos | `Tramo`, `LongitudM`, `GanaP1Seg` |
| Opcional | **Imagen** del mapa de minisectores | *Insertar → Imagen*, archivos de `reports/figures/*_mapa.png` |

Por qué: las columnas por tramo muestran dónde gana cada uno; la línea acumulada muestra cuándo se decide la diferencia final. El mapa de minisectores no se puede reproducir con visuales nativos, por eso se inserta como imagen (y está en vivo en `reports/dashboard.html`).

### Página 3 · Estrategia
*¿Qué estrategia fue mejor y cuánto se degradó cada neumático?* · datos: `fact_estrategias`, `fact_degradacion` y `fact_vueltas` (2024)

| Zona | Elemento | Campos |
|---|---|---|
| Arriba izquierda | **Segmentación** de GP | `dim_carrera[GranPremio]`, con un filtro de nivel visual `[Paradas medias]` *no está en blanco* para que solo salgan Baréin, Hungría e Italia |
| Fila superior | **3 tarjetas**: Paradas medias, Pérdida vs óptima (s), Degradación (s/vuelta) | medidas |
| Izquierda | **Barras**: segundos perdidos frente a la óptima por piloto | eje `dim_piloto[Abreviatura]`, valor `[Pérdida vs óptima (s)]`, ordenado por `PosicionFinal` |
| Centro | **Dispersión**: degradación | eje X `VidaNeumatico`, eje Y `TiempoCorregidoSeg` (promedio), detalles `Vuelta`, leyenda `dim_compuesto[Compuesto]` con colores por `ColorHex` |
| Derecha | **Columnas agrupadas**: degradación media por compuesto | eje `dim_compuesto[Compuesto]`, valor `[Degradación (s/vuelta)]` |
| Abajo | **Tabla**: estrategia real de cada piloto | `Abreviatura`, `PosicionFinal`, `Estrategia`, `Paradas`, `VsOptimaSeg` |

Por qué: la dispersión de vida del neumático frente a tiempo es *la* imagen de la degradación (pendiente = degradación); las barras de pérdida frente a la óptima responden a "¿quién decidió mejor?". Cuidado al interpretarlo: la "estrategia óptima" es un **modelo simplificado** (degradación lineal, sin tráfico, safety cars ni undercut), así que la comparación vale para ordenar, no como verdad absoluta.

Para colorear por compuesto: en el visual, *Formato → Colores de datos → fx* → **Valor de campo** → `dim_compuesto[ColorHex]`.

### Página 4 · Predicciones
*¿Acierta el modelo, y qué aporta frente a "los 3 primeros de la parrilla"?* · datos: `fact_predicciones` (2025-2026)

| Zona | Elemento | Campos |
|---|---|---|
| Arriba izquierda | **Segmentaciones** de Conjunto y GP | `fact_predicciones[Conjunto]`, `dim_carrera[GranPremio]` |
| Fila superior | **4 tarjetas**: % Acierto del modelo, % Acierto trivial, Podios sorpresa, Carreras | medidas |
| Izquierda | **Tabla de la carrera elegida**: pilotos ordenados por probabilidad | `Piloto`, `ParrillaAj`, `[Probabilidad de podio]` (con barras de datos), `PosicionReal`, `PredPodio`, `PodioReal` |
| Centro | **Columnas**: podios acertados (de 3) por carrera | eje `dim_carrera[Etiqueta]`, valor `[Podios acertados]`, escala 0-3 |
| Derecha | **Dispersión**: parrilla frente a probabilidad | X `ParrillaAj`, Y `[Probabilidad de podio]`, leyenda `PodioReal` |
| Abajo | **Matriz de confusión**: filas `PredPodio`, columnas `PodioReal`, valor `COUNTROWS` | |

Por qué: la tarjeta doble modelo-vs-trivial cuenta la historia honesta del proyecto (el modelo ordena mejor pero elige el mismo podio); la tabla de una carrera permite *ver* las probabilidades; la dispersión muestra que la parrilla domina la predicción.

### Pasos de ensamblado (cuando llegue el momento)

1. Crea las 4 páginas (pestañas inferiores) con los nombres de arriba.
2. Para cada página: **primero** las segmentaciones, **luego** las tarjetas (comprueba los valores de la tabla de "Esperado"), **después** los gráficos grandes.
3. **Ver → Sincronizar segmentaciones** si quieres que el año se mantenga entre páginas.
4. Guarda el informe y **Compartir → Copiar vínculo**, o **Archivo → Insertar en el sitio web (público)** si tu licencia lo permite (puede estar desactivado por tu universidad).
5. Haz capturas de cada página para el README del repositorio.

---

## 6. Equivalencias con Tableau Public

Si Power BI web no funciona con tu cuenta, **Tableau Public** es gratuito y tiene aplicación de escritorio para Mac. Los mismos archivos sirven: el Excel `modelo_f1.xlsx` o los CSV.

**Limitación a tener en cuenta:** todo lo que publiques en Tableau Public es **público** (también los datos). Aquí no hay problema: son datos públicos de F1.

### Conexión y modelo

1. Abre Tableau Public → **Conectar → Archivo de Microsoft Excel** → `modelo_f1.xlsx`. (Con CSV, **Archivo de texto**, uno por tabla; en ese caso añade las demás tablas arrastrándolas.)
2. En la pestaña de origen de datos (**capa lógica**) arrastra `fact_resultados` al lienzo y después las dimensiones. Tableau crea **relaciones** (líneas) por columnas con el mismo nombre; haz clic en cada línea y comprueba las claves de la tabla de la sección 3. Equivale al modelo de Power BI y no hace combinaciones (*joins*) hasta que las pides en una hoja.
3. Cada tabla de hechos con sus dimensiones forma una "estrella" distinta. Si en una misma hoja combinas resultados y vueltas, Tableau lo resuelve porque comparten `dim_carrera` y `dim_piloto`. Pero lo más sencillo es **un libro de trabajo (workbook) por fuente de hechos**, o trabajar con una fuente de datos por página.
4. **Piloto 1 y piloto 2 (doble rol):** añade `dim_piloto` **dos veces** al lienzo y relaciona cada copia con `Piloto1Id` y con `Piloto2Id`. Es el equivalente a la relación inactiva + `USERELATIONSHIP` de Power BI.

### Conceptos

| Power BI | Tableau Public |
|---|---|
| Informe / página | Libro de trabajo / **panel (dashboard)**; cada gráfico es una **hoja (worksheet)** |
| Visual | Hoja con "Marcas" (tarjeta de marcas) |
| Segmentación (slicer) | **Filtro** → clic derecho → *Mostrar filtro*; para propagarlo, *Aplicar a las hojas → Todas las que usan esta fuente* |
| Sincronizar segmentaciones | El mismo filtro aplicado a varias hojas |
| Tarjeta (KPI) | Hoja con un texto grande (el campo en *Texto*) |
| Top N en un visual | Filtro → pestaña **Principal** → *Por campo* |
| Formato condicional | Arrastrar la medida a **Color** y editar la paleta (divergente centrada en 0) |
| Información sobre herramientas | **Descripción emergente (tooltip)** |
| Ordenar por columna | Clic derecho en el campo → *Ordenar* → manual o por campo |
| Colores por `ColorHex` | Editar colores a mano (**Color → Editar colores**) con los hex de `dim_compuesto` |

### Medidas DAX → campos calculados

En Tableau se llaman **campos calculados** (*Análisis → Crear campo calculado*). Las expresiones de LOD (`{ FIXED ... }`) hacen el trabajo de `CALCULATE`.

| Medida (DAX) | Campo calculado en Tableau |
|---|---|
| `Puntos = SUM(Puntos)` | `SUM([Puntos])` |
| `Victorias`, `Podios`, `Abandonos` | `SUM([Victoria])`, `SUM([Podio])`, `SUM([Abandono])` |
| `Carreras = DISTINCTCOUNT(CarreraId)` | `COUNTD([CarreraId])` |
| `% Abandonos = DIVIDE(a, b)` | `SUM([Abandono]) / COUNT([Abandono])` (con `IF COUNT(...) > 0 THEN ... END` si puede haber 0) |
| `Posición media = AVERAGE(Posicion)` | `AVG([Posicion])` |
| `Puntos acumulados` (`CALCULATE` + `ALL`) | `RUNNING_SUM(SUM([Puntos]))` como **cálculo de tabla**: *calcular con* → `Etiqueta` (en el eje) y reiniciar por `Piloto` |
| `Ritmo medio (s)` | `AVG([TiempoCorregidoSeg])` |
| `Ritmo vs campo (s)` (`REMOVEFILTERS`) | `AVG([TiempoCorregidoSeg]) - { FIXED [CarreraId] : AVG([TiempoCorregidoSeg]) }` |
| `Mejor vuelta (s)` | `MIN([TiempoVueltaSeg])` |
| `Degradación (s/vuelta)` ponderada | `SUM([DegradacionSegVuelta] * [Vueltas]) / SUM([Vueltas])` |
| `Pérdida vs óptima (s)` | `AVG([VsOptimaSeg])` |
| `Ventaja acumulada P1 (s)` | `RUNNING_SUM(SUM([GanaP1Seg]))` calculado a lo largo de `OrdenTramo` |
| `Diferencia oficial de vuelta (s)` | `MAX([DifOficialSeg])` |
| `Tramos del piloto como piloto 2` (`USERELATIONSHIP`) | `COUNT([Piloto2Id])` usando la segunda copia de `dim_piloto` |
| `% Acierto del modelo` | `SUM([Acierto]) / SUM([PredPodio])` |
| `% Acierto trivial` | `SUM(IF [PredTrivial] = 1 AND [PodioReal] = 1 THEN 1 ELSE 0 END) / SUM([PredTrivial])` |
| `Podios sorpresa` | `SUM(IF [PodioReal] = 1 AND [PredPodio] = 0 THEN 1 ELSE 0 END)` |
| `Probabilidad de podio` | `AVG([ProbaPodioNorm])` |

Los valores **esperados** de la sección 4 son los mismos en Tableau: úsalos para comprobar cada campo calculado.

### Diferencias prácticas

- Tableau pide los tipos de campo: comprueba que `Fecha` es **Fecha**, que las claves están como **Dimensión** y las columnas numéricas como **Medida**.
- Un gráfico de **dispersión** necesita que ambas medidas estén en *columnas* y *filas* y que el nivel de detalle (`Vuelta`, `Piloto`) esté en **Detalle**; si no, verás un único punto.
- Para publicar: *Archivo → Guardar en Tableau Public* (requiere cuenta gratuita). El enlace resultante sirve para el portfolio y el CV.
