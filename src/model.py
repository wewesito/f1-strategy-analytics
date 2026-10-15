"""
model.py
Modelos, métricas y utilidades para la predicción de podios (fase 4).

Todos los modelos son `Pipeline` de scikit-learn: encadenan el preprocesado (imputar valores
perdidos, escalar) con el clasificador. Así el preprocesado se ajusta SOLO con el conjunto de
entrenamiento y no hay data leakage al validar o testear.

Este módulo no se ejecuta solo: lo importan el notebook 04_prediccion.ipynb y, más adelante, el pipeline.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import loguniform, randint, uniform
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEMILLA = 42


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


def pipeline_logistico(C=1.0):
    """
    Regresión logística con imputación, estandarización y class_weight='balanced'.
    - SimpleImputer: rellena los vacíos con la mediana del entrenamiento.
    - StandardScaler: media 0 y desviación 1, para que los coeficientes sean comparables.
    - class_weight='balanced': pesa más la clase minoritaria (los podios, ~15 %).
    """
    return Pipeline(
        [
            ('imputar', SimpleImputer(strategy='median')),
            ('escalar', StandardScaler()),
            ('logit', LogisticRegression(C=C, class_weight='balanced', max_iter=2000)),
        ]
    )


def pipeline_random_forest():
    """
    Random Forest: muchos árboles de decisión entrenados con muestras aleatorias de filas y variables;
    la predicción es la media de los árboles. No necesita escalar, pero sí rellenar vacíos.
    class_weight='balanced_subsample' reequilibra las clases en cada muestra de cada árbol.
    """
    return Pipeline(
        [
            ('imputar', SimpleImputer(strategy='median')),
            ('rf', RandomForestClassifier(class_weight='balanced_subsample', n_jobs=-1, random_state=SEMILLA)),
        ]
    )


def pipeline_gradient_boosting():
    """
    HistGradientBoostingClassifier: árboles pequeños entrenados EN SECUENCIA, cada uno corrige
    los errores del anterior. Admite NaN de forma nativa, así que no lleva imputador.
    """
    return Pipeline(
        [
            ('hgb', HistGradientBoostingClassifier(class_weight='balanced', random_state=SEMILLA)),
        ]
    )


# Espacios de búsqueda para RandomizedSearchCV: distribuciones de las que se sortean combinaciones
ESPACIO_RF = {
    'rf__n_estimators': randint(100, 500),
    'rf__max_depth': randint(3, 12),
    'rf__min_samples_leaf': randint(5, 60),  # hojas grandes = árboles más simples = menos sobreajuste
    'rf__max_features': uniform(0.3, 0.7),  # fracción de variables que ve cada nodo
}
ESPACIO_HGB = {
    'hgb__learning_rate': loguniform(0.01, 0.3),
    'hgb__max_iter': randint(50, 400),
    'hgb__max_depth': randint(2, 6),
    'hgb__min_samples_leaf': randint(10, 80),
    'hgb__l2_regularization': loguniform(1e-3, 10),
}


def cortes_temporales(df, n_splits=5):
    """
    Validación cruzada TEMPORAL por carreras. Aplica TimeSeriesSplit sobre la lista cronológica de
    carreras (no de filas) para que ninguna carrera quede partida entre entrenamiento y validación.
    Cada fold entrena con las carreras pasadas y valida con las siguientes (ventana creciente).
    Devuelve una lista de (índices_train, índices_validación) que se pasa como cv= a scikit-learn.
    """
    carrera = (df['Year'] * 100 + df['Round']).to_numpy()
    orden = np.unique(carrera)  # carreras en orden cronológico
    cortes = []
    for tr, va in TimeSeriesSplit(n_splits=n_splits).split(orden):
        cortes.append((np.where(np.isin(carrera, orden[tr]))[0], np.where(np.isin(carrera, orden[va]))[0]))
    return cortes


def buscar_hiperparametros(pipeline, espacio, X, y, df, n_iter=40, n_splits=5):
    """RandomizedSearchCV con validación cruzada temporal, optimizando el AUC-ROC (no depende del umbral)."""
    busqueda = RandomizedSearchCV(
        pipeline,
        espacio,
        n_iter=n_iter,
        scoring='roc_auc',
        cv=cortes_temporales(df, n_splits),
        random_state=SEMILLA,
        n_jobs=-1,
        refit=True,
    )
    return busqueda.fit(X, y)


def probabilidades_fuera_de_muestra(pipeline, X, y, df, n_splits=5):
    """
    Probabilidades 'fuera de muestra' sobre el conjunto de entrenamiento: cada fold de la CV temporal
    predice carreras que el modelo NO ha visto al ajustarse. Las filas de la primera ventana de
    entrenamiento (sin pasado) quedan como NaN. Sirve para analizar errores con más muestra que un solo año.
    """
    from sklearn.base import clone

    proba = pd.Series(np.nan, index=X.index)
    for idx_tr, idx_va in cortes_temporales(df, n_splits):
        m = clone(pipeline).fit(X.iloc[idx_tr], y.iloc[idx_tr])
        proba.iloc[idx_va] = m.predict_proba(X.iloc[idx_va])[:, 1]
    return proba


def abandono(df):
    """True si el piloto no vio la bandera a cuadros clasificado ('R' retirado, 'D' descalificado, 'W', 'N'...)."""
    return ~df['PositionText'].astype(str).str.isdigit()


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def metricas(y_real, proba, umbral=0.5):
    """Métricas de clasificación a partir de las probabilidades y un umbral de decisión."""
    pred = (np.asarray(proba) >= umbral).astype(int)
    return {
        'Accuracy': accuracy_score(y_real, pred),
        'Precisión': precision_score(y_real, pred, zero_division=0),
        'Recall': recall_score(y_real, pred, zero_division=0),
        'F1': f1_score(y_real, pred, zero_division=0),
        'AUC-ROC': roc_auc_score(y_real, proba),
    }


def matriz_confusion(y_real, proba, umbral=0.5):
    """DataFrame con la matriz de confusión (filas = real, columnas = predicho)."""
    pred = (np.asarray(proba) >= umbral).astype(int)
    cm = confusion_matrix(y_real, pred, labels=[0, 1])
    return pd.DataFrame(cm, index=['Real: no podio', 'Real: podio'], columns=['Pred: no podio', 'Pred: podio'])


def predecir_top3(df, proba):
    """
    Regla de decisión por carrera: en cada Gran Premio se marcan como podio los 3 pilotos con mayor
    probabilidad. Como siempre hay exactamente 3 podios, es una regla más natural que un umbral fijo.
    Devuelve un array de 0/1 alineado con las filas de df.
    """
    tmp = pd.DataFrame({'Year': df['Year'].values, 'Round': df['Round'].values, 'proba': np.asarray(proba)})
    puesto = tmp.groupby(['Year', 'Round'])['proba'].rank(ascending=False, method='first')
    return (puesto <= 3).astype(int).values


def metricas_top3(y_real, df, proba):
    """Métricas de la regla 'los 3 con más probabilidad de cada carrera'. Con 3 elegidos y 3 podios,
    precisión = recall = F1: es el % de podios que acertamos."""
    pred = predecir_top3(df, proba)
    return {
        'Accuracy': accuracy_score(y_real, pred),
        'Precisión': precision_score(y_real, pred, zero_division=0),
        'Recall': recall_score(y_real, pred, zero_division=0),
        'F1': f1_score(y_real, pred, zero_division=0),
        'AUC-ROC': roc_auc_score(y_real, proba),
    }


def pred_trivial_parrilla(df):
    """Modelo trivial: 'los 3 primeros de la parrilla hacen podio'. No aprende nada de los datos."""
    return (df['GridAdj'] <= 3).astype(int).values


def metricas_trivial(y_real, df):
    """Métricas del modelo trivial. Para el AUC se usa -GridAdj como puntuación (salir antes = más probable)."""
    pred = pred_trivial_parrilla(df)
    return {
        'Accuracy': accuracy_score(y_real, pred),
        'Precisión': precision_score(y_real, pred, zero_division=0),
        'Recall': recall_score(y_real, pred, zero_division=0),
        'F1': f1_score(y_real, pred, zero_division=0),
        'AUC-ROC': roc_auc_score(y_real, -df['GridAdj']),
    }


# ---------------------------------------------------------------------------
# Interpretación de la regresión logística
# ---------------------------------------------------------------------------


def tabla_coeficientes(modelo, features):
    """
    Coeficientes de la regresión logística, al estilo de la salida de un glm en R.
    - Coef (std): cambio en el log-odds por cada +1 desviación típica de la variable.
    - Odds ratio (std): exp(coef). >1 sube la probabilidad de podio, <1 la baja.
    - Odds ratio (unidad): el mismo efecto por cada +1 unidad real de la variable.
    """
    logit = modelo.named_steps['logit']
    escala = modelo.named_steps['escalar'].scale_
    coef = logit.coef_[0]
    return pd.DataFrame(
        {
            'Coef (std)': coef,
            'Odds ratio (std)': np.exp(coef),
            'Odds ratio (unidad)': np.exp(coef / escala),
        },
        index=features,
    ).sort_values('Coef (std)', key=abs, ascending=False)


def bootstrap_coeficientes(X, y, n=300, semilla=SEMILLA):
    """
    Intervalos de confianza de los coeficientes por bootstrap (remuestreo con reemplazo).
    scikit-learn no da p-valores como R; el bootstrap es una alternativa sin instalar nada más.
    """
    rng = np.random.default_rng(semilla)
    coefs = []
    for _ in range(n):
        idx = rng.integers(0, len(X), len(X))
        m = pipeline_logistico().fit(X.iloc[idx], y.iloc[idx])
        coefs.append(m.named_steps['logit'].coef_[0])
    coefs = np.array(coefs)
    return pd.DataFrame(
        {'IC 2.5 %': np.percentile(coefs, 2.5, axis=0), 'IC 97.5 %': np.percentile(coefs, 97.5, axis=0)},
        index=X.columns,
    )


# ---------------------------------------------------------------------------
# Guardar modelos y exportar predicciones
# ---------------------------------------------------------------------------


def reajustar(pipeline, df_train, features, target='Podio'):
    """Clona el pipeline (con sus hiperparámetros ya elegidos) y lo ajusta de nuevo con df_train."""
    from sklearn.base import clone

    return clone(pipeline).fit(df_train[features], df_train[target])


def guardar_modelo(modelo, ruta, metadatos):
    """
    Guarda el modelo con joblib (formato eficiente para objetos de scikit-learn) y un JSON con sus metadatos.
    Se guarda la versión de scikit-learn: un modelo serializado solo es seguro de cargar con la misma versión.
    """
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    joblib.dump(modelo, ruta)
    meta = dict(metadatos, sklearn=sklearn.__version__)
    with open(os.path.splitext(ruta)[0] + '.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def cargar_modelo(ruta):
    """Carga un modelo guardado con guardar_modelo()."""
    return joblib.load(ruta)


def tabla_predicciones(df, proba, conjunto, nombre_modelo):
    """
    Una fila por piloto y carrera con la probabilidad de podio.
    - Proba: probabilidad que devuelve el modelo (con class_weight='balanced' tiende a ser alta).
    - ProbaNorm: la misma probabilidad reescalada para que sume 3 en cada carrera (siempre hay 3 podios).
    - PredPodio: 1 para los 3 pilotos con más probabilidad de la carrera.
    """
    t = df[
        ['Year', 'Round', 'Event', 'Date', 'Abbreviation', 'DriverId', 'TeamName', 'GridAdj', 'Position', 'Podio']
    ].copy()
    # Se redondea a 6 decimales para que el CSV sea idéntico se genere desde el notebook o desde el pipeline
    t['Proba'] = np.asarray(proba).round(6)
    t['ProbaNorm'] = (t['Proba'] * 3 / t.groupby(['Year', 'Round'])['Proba'].transform('sum')).clip(upper=1).round(6)
    t['RankProba'] = t.groupby(['Year', 'Round'])['Proba'].rank(ascending=False, method='first').astype(int)
    t['PredPodio'] = (t['RankProba'] <= 3).astype(int)
    t['Conjunto'] = conjunto
    t['Modelo'] = nombre_modelo
    return t.rename(columns={'Position': 'PosicionReal', 'Podio': 'PodioReal'})


def actualizar_predicciones(
    ruta_csv=os.path.join('data', 'processed', 'predicciones_podio.csv'),
    ruta_modelo=os.path.join('models', 'modelo_podio.joblib'),
    ultimo_anio_entrenamiento=2025,
):
    """
    Añade (o actualiza) las predicciones de las carreras posteriores al entrenamiento ("en vivo") con el modelo
    guardado. Las filas de años <= ultimo_anio_entrenamiento (test 2025) se conservan tal cual.
    Devuelve el número de carreras en vivo predichas.
    """
    import features as ft  # import local: evita un ciclo si features importara model algún día

    datos = ft.cargar_datos()
    vivo = datos[datos['Year'] > ultimo_anio_entrenamiento]
    if vivo.empty:
        return 0
    modelo = cargar_modelo(ruta_modelo)
    nuevas = []
    for year, g in vivo.groupby('Year'):
        proba = modelo.predict_proba(g[ft.FEATURES])[:, 1]
        nuevas.append(
            tabla_predicciones(
                g, proba, f'En vivo {year} (modelo hasta {ultimo_anio_entrenamiento})', 'Gradient Boosting'
            )
        )

    previas = pd.read_csv(ruta_csv)
    previas = previas[previas['Year'] <= ultimo_anio_entrenamiento]
    pd.concat([previas] + nuevas, ignore_index=True).to_csv(ruta_csv, index=False)
    return int(vivo.groupby(['Year', 'Round']).ngroups)
