"""
model.py
Modelos, métricas y utilidades para la predicción de podios (fase 4).

Todos los modelos son `Pipeline` de scikit-learn: encadenan el preprocesado (imputar valores
perdidos, escalar) con el clasificador. Así el preprocesado se ajusta SOLO con el conjunto de
entrenamiento y no hay data leakage al validar o testear.

Este módulo no se ejecuta solo: lo importan el notebook 04_prediccion.ipynb y, más adelante, el pipeline.
"""

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
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
    return Pipeline([
        ('imputar', SimpleImputer(strategy='median')),
        ('escalar', StandardScaler()),
        ('logit', LogisticRegression(C=C, class_weight='balanced', max_iter=2000)),
    ])


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
    return pd.DataFrame(cm, index=['Real: no podio', 'Real: podio'],
                        columns=['Pred: no podio', 'Pred: podio'])


def predecir_top3(df, proba):
    """
    Regla de decisión por carrera: en cada Gran Premio se marcan como podio los 3 pilotos con mayor
    probabilidad. Como siempre hay exactamente 3 podios, es una regla más natural que un umbral fijo.
    Devuelve un array de 0/1 alineado con las filas de df.
    """
    tmp = pd.DataFrame({'Year': df['Year'].values, 'Round': df['Round'].values,
                        'proba': np.asarray(proba)})
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
    return pd.DataFrame({
        'Coef (std)': coef,
        'Odds ratio (std)': np.exp(coef),
        'Odds ratio (unidad)': np.exp(coef / escala),
    }, index=features).sort_values('Coef (std)', key=abs, ascending=False)


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
    return pd.DataFrame({'IC 2.5 %': np.percentile(coefs, 2.5, axis=0),
                         'IC 97.5 %': np.percentile(coefs, 97.5, axis=0)}, index=X.columns)
