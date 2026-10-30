"""Instala la configuración "Mi Jarvis en español" en ~/.openjarvis.

Uso (desde la carpeta del repo):
    uv run python scripts/mi_jarvis/instalar.py            # instalar o actualizar
    uv run python scripts/mi_jarvis/instalar.py --forzar   # volver a los originales

Hace cuatro cosas:
  1. Copia el preset mi-jarvis-es como config.toml.
  2. Copia la personalidad (SOUL.md) y tu perfil (USER.md).
  3. Copia la voz del resumen de la mañana en español (jarvis_es).
  4. Crea (o actualiza) los agentes programados de Jarvis:
     - "Jarvis · Salud": mensaje de salud cada mañana por Telegram.
     - "Jarvis · Correos": revisa tus correos cada 30 minutos y te avisa por
       WhatsApp de los importantes.

Si ya personalizaste config.toml, SOUL.md o USER.md, se conservan tal cual (para
reemplazarlos usa --forzar; antes se guarda una copia de respaldo). Así puedes
volver a ejecutarlo para actualizar los agentes sin perder tus datos.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from openjarvis.core.paths import get_config_dir

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
PRESET = REPO / "configs" / "openjarvis" / "examples" / "mi-jarvis-es.toml"
PERSONA = REPO / "configs" / "openjarvis" / "prompts" / "personas" / "jarvis_es.md"

# Agentes programados: nombre → (tipo de agente, configuración del horario).
AGENTES = {
    "Jarvis · Salud": (
        "jarvis_salud",
        {
            "schedule_type": "cron",
            "schedule_value": "0 7 * * *",  # todos los días a las 7:00
            "instruction": "Envía el mensaje de salud de la mañana.",
        },
    ),
    "Jarvis · Correos": (
        "jarvis_correos",
        {
            "schedule_type": "interval",
            "schedule_value": 1800,  # cada 30 minutos
            "instruction": "Revisa los correos nuevos y avisa de los importantes.",
        },
    ),
}


def copiar(origen: Path, destino: Path, *, conservar_si: str = "") -> None:
    """Copia *origen* a *destino*, respaldando el archivo previo si cambia.

    Si *destino* ya contiene el texto *conservar_si*, es una versión de Mi
    Jarvis que el usuario personalizó: se conserva salvo con ``--forzar``.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        actual = destino.read_text(encoding="utf-8", errors="replace")
        if destino.read_bytes() == origen.read_bytes():
            print(f"  = {destino} (sin cambios)")
            return
        if conservar_si and conservar_si in actual and "--forzar" not in sys.argv:
            print(f"  = {destino} (conservo tu versión personalizada)")
            return
        respaldo = destino.with_name(f"{destino.name}.respaldo-{int(time.time())}")
        shutil.copy2(destino, respaldo)
        print(f"  ↺ respaldo de tu versión anterior: {respaldo}")
    shutil.copyfile(origen, destino)
    print(f"  ✓ {destino}")


def crear_agentes() -> None:
    """Crea los agentes de Jarvis, o actualiza su horario si ya existen."""
    from openjarvis.agents.manager import AgentManager
    from openjarvis.core.config import load_config

    cfg = load_config()
    manager = AgentManager(db_path=cfg.agent_manager.db_path)
    existentes = {a["name"]: a for a in manager.list_agents()}
    for nombre, (tipo, horario) in AGENTES.items():
        config = {**horario, "timezone": cfg.digest.timezone}
        if nombre in existentes:
            agente = existentes[nombre]
            manager.update_agent(agente["id"], agent_type=tipo, config=config)
            print(f"  = agente {nombre!r} actualizado")
        else:
            manager.create_agent(nombre, agent_type=tipo, config=config)
            print(f"  ✓ agente {nombre!r} creado")


def main() -> None:
    home = get_config_dir()
    print(f"Instalando Mi Jarvis en {home}\n")
    copiar(PRESET, home / "config.toml", conservar_si="[jarvis]")
    copiar(AQUI / "SOUL.md", home / "SOUL.md", conservar_si="# Personalidad de Jarvis")
    copiar(AQUI / "USER.md", home / "USER.md", conservar_si="# Perfil del usuario")
    copiar(PERSONA, home / "prompts" / "personas" / "jarvis_es.md")
    crear_agentes()
    print(
        "\nListo. Siguiente paso: completa [jarvis] en config.toml, define"
        " ANTHROPIC_API_KEY y TELEGRAM_BOT_TOKEN (ver scripts/mi_jarvis/LEEME.md)"
        " y ejecuta: uv run jarvis doctor"
    )


if __name__ == "__main__":
    main()
