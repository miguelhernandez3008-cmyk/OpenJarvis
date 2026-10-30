"""Vincula WhatsApp con Jarvis escaneando un código QR (una sola vez).

Uso (desde la carpeta del repo):
    uv run python scripts/mi_jarvis/vincular_whatsapp.py

Funciona como WhatsApp Web: Jarvis queda como un "dispositivo vinculado" de
tu WhatsApp y te escribe en el chat contigo mismo ("Tú" / "Mensaje a ti mismo").
Requiere Node.js 22 o superior.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time

from openjarvis.agents.jarvis_avisos import _normalize_spec
from openjarvis.channels.whatsapp_baileys import _BRIDGE_SRC, WhatsAppBaileysChannel
from openjarvis.core.config import load_config


def npm(*args: str, cwd: str) -> None:
    exe = shutil.which("npm")  # npm.cmd en Windows
    if exe is None:
        sys.exit("No encontré npm. Instala Node.js 22+ desde https://nodejs.org")
    subprocess.run([exe, *args], cwd=cwd, check=True)


def main() -> None:
    cfg = load_config()
    canal = WhatsAppBaileysChannel(auth_dir=cfg.channel.whatsapp_baileys.auth_dir)

    # 1. Compilar el puente de WhatsApp si hace falta.
    if not (_BRIDGE_SRC / "dist" / "bridge.js").exists():
        print("Compilando el puente de WhatsApp (solo la primera vez)…")
        npm("install", "--no-audit", "--no-fund", cwd=str(_BRIDGE_SRC))
        npm("run", "build", cwd=str(_BRIDGE_SRC))
    runtime = canal._runtime_dir
    runtime.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_BRIDGE_SRC / "package.json", runtime / "package.json")
    if not (runtime / "node_modules").exists():
        npm("install", "--omit=dev", "--no-audit", "--no-fund", cwd=str(runtime))
    bridge_js = canal._ensure_bridge()
    auth = canal._auth_dir or str(runtime / "auth")

    # 2. Mostrar el QR y esperar a que el teléfono lo escanee.
    print(
        "\nEn tu celular abre WhatsApp → Configuración → Dispositivos vinculados →"
        " Vincular un dispositivo, y escanea el QR que aparece abajo.\n"
    )
    proc = subprocess.Popen(
        ["node", str(bridge_js), "--auth-dir", auth],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "status" and event.get("status") == "connected":
                break
            if event.get("type") == "error":
                print(f"Error de WhatsApp: {event.get('message')}")
        else:
            sys.exit("El puente de WhatsApp se cerró antes de vincularse.")

        print("\n✅ WhatsApp vinculado.")
        destino = cfg.jarvis.email_channel
        if destino.startswith("whatsapp_baileys:") and destino.partition(":")[2]:
            jid = _normalize_spec(destino).partition(":")[2]
            mensaje = (
                "Hola, soy Jarvis 👋 Desde ahora te aviso aquí de tus correos"
                " importantes."
            )
            comando = {"type": "send", "jid": jid, "text": mensaje}
            proc.stdin.write(json.dumps(comando) + "\n")
            proc.stdin.flush()
            print("Te envié un mensaje de prueba. Revisa el chat contigo mismo.")
            time.sleep(5)
        else:
            print(
                "Ahora pon tu número en config.toml:"
                ' email_channel = "whatsapp_baileys:57XXXXXXXXXX"'
            )
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
