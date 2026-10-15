"""
Configuración común de pytest.
- Añade src/ al path para poder hacer `import features`, `import extract`...
- Se ejecuta siempre desde la raíz del proyecto, porque todas las rutas del proyecto son relativas a ella.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'src'))
os.chdir(RAIZ)
