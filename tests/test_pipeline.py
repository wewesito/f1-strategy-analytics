"""Tests de la lógica de la descarga incremental (sin conectarse a ninguna API)."""

import pandas as pd

import extract


def calendario():
    return pd.DataFrame({
        'RoundNumber': [1, 2, 3, 4],
        'EventName': ['GP1', 'GP2', 'GP3', 'GP4'],
        'Session5DateUtc': pd.to_datetime(['2026-03-01 14:00', '2026-03-15 14:00', '2026-03-29 14:00', '2026-04-12 14:00']),
    })


def test_solo_pide_las_carreras_disputadas_que_faltan():
    ahora = pd.Timestamp('2026-03-30 12:00', tz='UTC')
    pendientes = extract.rondas_pendientes(calendario(), descargadas={1}, ahora=ahora)
    assert pendientes['RoundNumber'].tolist() == [2, 3]          # la 1 ya está y la 4 aún no se ha corrido


def test_una_carrera_recien_terminada_se_espera_tres_horas():
    cal = calendario()
    justo_despues = pd.Timestamp('2026-03-01 15:00', tz='UTC')        # 1 h después de la salida simulada
    assert extract.rondas_pendientes(cal, set(), ahora=justo_despues).empty
    mas_tarde = pd.Timestamp('2026-03-01 18:00', tz='UTC')
    assert extract.rondas_pendientes(cal, set(), ahora=mas_tarde)['RoundNumber'].tolist() == [1]


def test_sin_carreras_nuevas_no_hay_pendientes():
    ahora = pd.Timestamp('2026-12-31', tz='UTC')
    assert extract.rondas_pendientes(calendario(), {1, 2, 3, 4}, ahora=ahora).empty


def test_rondas_descargadas_sin_archivo(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, 'OUTPUT_DIR', str(tmp_path))
    assert extract.rondas_descargadas(2099) == set()


def test_rondas_descargadas_lee_las_rondas_del_archivo(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, 'OUTPUT_DIR', str(tmp_path))
    pd.DataFrame({'Round': [1, 1, 2, 5]}).to_parquet(tmp_path / 'laps_2099.parquet')
    assert extract.rondas_descargadas(2099) == {1, 2, 5}
