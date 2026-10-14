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
