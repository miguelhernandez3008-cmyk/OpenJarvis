"""Prueba la voz de Jarvis en español.

Uso (desde la carpeta del repo):
    uv run python scripts/mi_jarvis/probar_voz.py

La primera vez descarga el modelo de voz (unos 300 MB). Guarda el audio en
~/.openjarvis/prueba_voz.wav y lo reproduce por los parlantes.
"""

from __future__ import annotations

from openjarvis.core.config import load_config
from openjarvis.core.paths import get_config_dir
from openjarvis.speech.kokoro_tts import KokoroTTSBackend
from openjarvis.speech.voice_io import play_wav

TEXTO = (
    "Hola Miguel, soy Jarvis. Desde ahora te voy a hablar en español. "
    "Recuerda tomar agua y salir a caminar un rato hoy."
)


def main() -> None:
    voz = load_config().speech.voice_id or "em_alex"
    print(f"Generando audio con la voz {voz}… (la primera vez tarda un poco)")
    resultado = KokoroTTSBackend(device="cpu").synthesize(TEXTO, voice_id=voz)
    destino = get_config_dir() / "prueba_voz.wav"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(resultado.audio)
    print(f"✓ Audio guardado en {destino} ({resultado.duration_seconds:.1f} s)")
    try:
        play_wav(resultado.audio)
        print("✓ Reproducido. ¿Lo escuchaste?")
    except Exception as exc:  # noqa: BLE001
        print(f"No pude reproducirlo ({exc}). Abre el archivo de arriba para oírlo.")


if __name__ == "__main__":
    main()
