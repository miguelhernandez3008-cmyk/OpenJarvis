"""Instala la configuración "Mi Jarvis en español" en ~/.openjarvis.

Uso (desde la carpeta del repo):
    uv run python scripts/mi_jarvis/instalar.py

Hace tres cosas:
  1. Copia el preset mi-jarvis-es como config.toml (respaldando el anterior).
  2. Copia la personalidad (SOUL.md) y tu perfil (USER.md), respaldando los tuyos.
  3. Copia la voz del resumen de la mañana en español (jarvis_es).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from openjarvis.core.paths import get_config_dir

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
PRESET = REPO / "configs" / "openjarvis" / "examples" / "mi-jarvis-es.toml"
PERSONA = REPO / "configs" / "openjarvis" / "prompts" / "personas" / "jarvis_es.md"


def copiar(origen: Path, destino: Path) -> None:
    """Copia *origen* a *destino*, respaldando el archivo previo si cambia."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        if destino.read_bytes() == origen.read_bytes():
            print(f"  = {destino} (sin cambios)")
            return
        respaldo = destino.with_name(f"{destino.name}.respaldo-{int(time.time())}")
        shutil.copy2(destino, respaldo)
        print(f"  ↺ respaldo de tu versión anterior: {respaldo}")
    shutil.copyfile(origen, destino)
    print(f"  ✓ {destino}")


def main() -> None:
    home = get_config_dir()
    print(f"Instalando Mi Jarvis en {home}\n")
    copiar(PRESET, home / "config.toml")
    copiar(AQUI / "SOUL.md", home / "SOUL.md")
    copiar(AQUI / "USER.md", home / "USER.md")
    copiar(PERSONA, home / "prompts" / "personas" / "jarvis_es.md")
    print(
        "\nListo. Siguiente paso: define ANTHROPIC_API_KEY y TELEGRAM_BOT_TOKEN"
        " (ver scripts/mi_jarvis/LEEME.md) y ejecuta: uv run jarvis doctor"
    )


if __name__ == "__main__":
    main()
