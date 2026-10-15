"""Tests de summary.py con un cliente falso: no se llama a la API ni se gasta nada."""

import json
from types import SimpleNamespace

import pytest

import summary


class ClienteFalso:
    """Imita lo mínimo de anthropic.Anthropic().messages.create y guarda cómo se le llamó."""

    def __init__(self, texto='Resumen de prueba.', stop_reason='end_turn'):
        self.llamadas = []
        self._respuesta = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type='thinking', thinking=''), SimpleNamespace(type='text', text=texto)],
        )
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.llamadas.append(kwargs)
        return self._respuesta


@pytest.fixture
def datos():
    return summary.paquete_de_datos(202517)  # una carrera de 2025 con predicción en el modelo en estrella


def test_la_ultima_carrera_es_la_mas_reciente_del_anio():
    assert summary.ultima_carrera(2025) == 202524
    assert summary.ultima_carrera(1999) is None


def test_el_paquete_de_datos_contiene_solo_lo_esperado(datos):
    assert set(datos) >= {
        'carrera',
        'resultado_top10',
        'abandonos_o_no_clasificados',
        'clasificacion_pilotos_tras_la_carrera',
        'prediccion_del_modelo',
    }
    assert len(datos['resultado_top10']) == 10
    assert [r['posicion'] for r in datos['resultado_top10']] == list(range(1, 11))
    assert len(datos['prediccion_del_modelo']['top3_predicho']) == 3


def test_sin_predicciones_para_2024_el_paquete_no_las_incluye():
    d = summary.paquete_de_datos(202416)
    assert 'prediccion_del_modelo' not in d
    assert d['carrera']['gran_premio'] == 'Italian Grand Prix'
    assert d['lluvia']['porcentaje_de_vueltas_limpias_con_lluvia'] >= 0


def test_se_envia_el_modelo_los_datos_y_las_reglas(datos):
    cliente = ClienteFalso()
    texto = summary.generar_resumen(cliente, 'modelo-de-prueba', datos)
    assert texto == 'Resumen de prueba.'
    llamada = cliente.llamadas[0]
    assert llamada['model'] == 'modelo-de-prueba'
    assert 'EXCLUSIVAMENTE' in llamada['system']
    contenido = llamada['messages'][0]['content']
    assert json.dumps(datos['carrera']['gran_premio'], ensure_ascii=False) in contenido
    assert llamada['max_tokens'] >= 2000  # margen para el razonamiento adaptativo
    assert 'temperature' not in llamada  # Sonnet 5.5 rechaza temperaturas no predeterminadas


@pytest.mark.parametrize('stop', ['refusal', 'max_tokens'])
def test_respuestas_no_utilizables_lanzan_error(datos, stop):
    with pytest.raises(RuntimeError):
        summary.generar_resumen(ClienteFalso(stop_reason=stop), 'm', datos)


def test_respuesta_sin_texto_lanza_error(datos):
    with pytest.raises(RuntimeError):
        summary.generar_resumen(ClienteFalso(texto='   '), 'm', datos)


def test_guardar_crea_un_archivo_por_carrera(tmp_path, datos):
    ruta = summary.guardar('Texto de prueba con cinco palabras.', datos, 'modelo-x', carpeta=str(tmp_path))
    assert ruta.endswith(summary.nombre_archivo(datos))
    contenido = open(ruta, encoding='utf-8').read()
    assert 'modelo: modelo-x' in contenido and 'Texto de prueba' in contenido
    assert summary.nombre_archivo(datos).startswith('2025_R17_')


def test_sin_clave_no_llama_a_la_api_ni_crea_archivos(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(summary, 'SALIDA', str(tmp_path))
    assert summary.main(['--year', '2025']) == 0
    assert 'ANTHROPIC_API_KEY' in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_dry_run_usa_el_modelo_por_defecto_si_la_variable_esta_vacia(monkeypatch, capsys):
    monkeypatch.setenv('ANTHROPIC_MODEL', '')
    assert summary.main(['--year', '2025', '--dry-run']) == 0
    assert 'Modelo: claude-sonnet-5-5' in capsys.readouterr().out
    monkeypatch.setenv('ANTHROPIC_MODEL', 'otro-modelo')
    summary.main(['--year', '2025', '--dry-run'])
    assert 'Modelo: otro-modelo' in capsys.readouterr().out


def test_no_hay_ninguna_clave_escrita_en_el_codigo():
    import re

    codigo = open('src/summary.py', encoding='utf-8').read()
    assert not re.search(r'sk-ant-[A-Za-z0-9_-]{10,}', codigo)
