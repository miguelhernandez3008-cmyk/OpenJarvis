# Mi Jarvis en español: guía de instalación (Windows)

Esta configuración deja a Jarvis:

- **Respondiendo siempre en español**, en el chat y en el resumen de la mañana (también por voz).
- **Conectado a Telegram**, para hablarle desde el celular.
- **Usando Claude en la nube**, así no necesitas una computadora potente.
- **Mandándote avisos solo**:
  - 🩺 **Salud**: cada mañana a las 7:00 te manda por Telegram un mensaje de salud (tu calendario, el clima y tus metas).
  - 📬 **Correos**: cada 30 minutos revisa tu Gmail y te avisa por WhatsApp **solo** de los correos importantes. Nunca repite uno que ya te avisó.

Los avisos llegan como **texto y nota de voz** (con la voz en español de Jarvis), si instalaste la voz.

> **¿Usas Chromebook o Linux?** Sigue la sección [Chromebook / Linux](#chromebook--linux) al final:
> los pasos son los mismos, pero cambian algunos comandos.

---

## 1. Instala los programas base (una sola vez)

Abre **PowerShell** y ejecuta:

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
```

Node.js hace falta para WhatsApp y para la interfaz gráfica.
Cierra PowerShell y ábrelo de nuevo para que reconozca los programas.

## 2. Descarga tu copia del proyecto

```powershell
git clone -b personalizacion-es https://github.com/miguelhernandez3008-cmyk/OpenJarvis.git "$env:LOCALAPPDATA\OpenJarvis\src"
cd "$env:LOCALAPPDATA\OpenJarvis\src"
uv sync --extra inference-cloud --extra channel-telegram --extra voice --extra server
```

La primera vez tarda unos minutos. Desde aquí, todos los comandos se ejecutan dentro de esa carpeta.

## 3. Consigue tu clave de Claude

1. Entra en <https://console.anthropic.com>, crea una cuenta y agrega saldo (con 5 USD alcanza para bastante uso).
2. Ve a **API Keys**, luego **Create Key**, y copia la clave (empieza con `sk-ant-`).
3. Guárdala en Windows (cambia el texto por tu clave):

```powershell
setx ANTHROPIC_API_KEY "sk-ant-PEGA-TU-CLAVE-AQUI"
```

## 4. Crea tu bot de Telegram

1. En Telegram, busca **@BotFather** y envíale `/newbot`.
2. Elige un nombre (por ejemplo `Mi Jarvis`) y un usuario que termine en `bot` (por ejemplo `miguel_jarvis_bot`).
3. BotFather te da un **token** como `123456789:ABC...`. Guárdalo así:

```powershell
setx TELEGRAM_BOT_TOKEN "PEGA-TU-TOKEN-AQUI"
```

4. Busca **@userinfobot** en Telegram y envíale cualquier mensaje. Te responde con tu **Id** (un número). Lo usarás en el paso 5.
5. Abre el chat con **tu** bot y pulsa **Iniciar**. Si no lo haces, Telegram no le permite escribirte.

Cierra PowerShell y ábrelo de nuevo para que tome las claves.

## 5. Instala la configuración

```powershell
cd "$env:LOCALAPPDATA\OpenJarvis\src"
uv run python scripts/mi_jarvis/instalar.py
```

Esto copia la configuración y crea los dos agentes de Jarvis (**Salud** y **Correos**). Luego abre la configuración:

```powershell
notepad $HOME\.openjarvis\config.toml
```

y completa estos datos (cambia los números por los tuyos):

| Línea | Qué poner | Ejemplo |
|---|---|---|
| `allowed_chat_ids` | Tu Id de Telegram, para que el bot solo te responda a ti | `allowed_chat_ids = "123456789"` |
| `health_channel` | `telegram:` + tu Id de Telegram | `health_channel = "telegram:123456789"` |
| `email_channel` | `whatsapp_baileys:` + tu número con código de país, sin `+` | `email_channel = "whatsapp_baileys:573001234567"` |
| `timezone` | Tu zona horaria | `"America/Bogota"`, `"America/Mexico_City"` o `"Europe/Madrid"` |

Si cambias la zona horaria, vuelve a ejecutar `instalar.py` para que los agentes usen la hora correcta.

Edita también tus metas de salud (agua, ejercicio, medicamentos…) en:

```powershell
notepad $HOME\.openjarvis\USER.md
```

## 6. Conecta Gmail, Calendar y WhatsApp (una sola vez)

```powershell
uv run jarvis connect gdrive                      # Gmail, Calendar y Tasks con tu cuenta de Google
uv run python scripts/mi_jarvis/vincular_whatsapp.py
```

El segundo comando muestra un **código QR**. En tu celular abre **WhatsApp → Configuración → Dispositivos vinculados → Vincular un dispositivo** y escanéalo. Jarvis te enviará un mensaje de prueba en el chat **contigo mismo**.

> ⚠️ **Sobre WhatsApp:** esta conexión funciona como WhatsApp Web (un "dispositivo vinculado"). No es la API oficial para empresas, así que WhatsApp podría limitarla. Como Jarvis solo te escribe a ti y pocas veces, el riesgo es bajo. Si algún día deja de funcionar, cambia `email_channel` a `telegram:TU_ID` y los avisos de correos te llegarán por Telegram.

## 7. ¡A usarlo!

```powershell
uv run jarvis doctor     # revisa que todo esté bien
uv run jarvis chat       # chatea en la terminal
uv run jarvis gui        # interfaz gráfica en el navegador
uv run jarvis serve      # Jarvis completo: bot de Telegram + avisos de salud y correos
```

**Importante:** los avisos y el bot de Telegram solo funcionan mientras `jarvis serve` está corriendo y la computadora está encendida.

### Que Jarvis arranque solo al encender la computadora

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\jarvis-service.ps1 install
```

Para quitarlo: el mismo comando cambiando `install` por `uninstall`.

### Resumen de la mañana con voz

```powershell
uv run jarvis digest --fresh   # genera y reproduce el resumen
```

> **Voz en español:** la voz local (Kokoro) necesita **espeak-ng**. Instálalo con
> `winget install --id eSpeak-NG.eSpeak-NG -e`. Si no te funciona, puedes generar
> solo el texto con `uv run jarvis digest --fresh --text-only`.

---

## Personalizar

| Quiero cambiar… | Dónde |
|---|---|
| La personalidad de Jarvis en el chat | `~/.openjarvis/SOUL.md` |
| Lo que Jarvis sabe de mí y mis metas de salud | `~/.openjarvis/USER.md` |
| A dónde llegan los avisos, o qué fuentes revisa | sección `[jarvis]` de `~/.openjarvis/config.toml` |
| La hora del mensaje de salud o cada cuánto revisa correos | `AGENTES` en `scripts/mi_jarvis/instalar.py`, y luego vuelve a ejecutarlo |
| Qué considera "correo importante" | `_CORREOS_PROMPT` en `src/openjarvis/agents/jarvis_avisos.py` |
| El modelo o las herramientas del chat | `~/.openjarvis/config.toml` |

Los originales están en esta carpeta (`scripts/mi_jarvis/`) y en `configs/openjarvis/examples/mi-jarvis-es.toml`.
Puedes volver a ejecutar `instalar.py` cuando quieras: **conserva** tu `config.toml`, `SOUL.md` y `USER.md`
y solo actualiza los agentes. Para volver a los originales usa `instalar.py --forzar`; antes guarda una copia
de respaldo de tus archivos (`*.respaldo-…`).

---

## Chromebook / Linux

Todo se hace en la **terminal de Linux**. Cambia estos pasos:

| Paso | En Chromebook / Linux |
|---|---|
| 1. Programas base | `sudo apt update && sudo apt install -y git curl`, luego `curl -LsSf https://astral.sh/uv/install.sh \| sh`, `curl -fsSL https://deb.nodesource.com/setup_22.x \| sudo -E bash -` y `sudo apt install -y nodejs` |
| 2. Descargar | `git clone -b personalizacion-es https://github.com/miguelhernandez3008-cmyk/OpenJarvis.git ~/OpenJarvis`, luego `cd ~/OpenJarvis` y `uv sync --extra inference-cloud --extra channel-telegram --extra server` |
| Voz (opcional) | `sudo apt install -y espeak-ng libportaudio2` y `uv pip install --torch-backend cpu "kokoro>=0.9" soundfile sounddevice`. Pruébala con `uv run python scripts/mi_jarvis/probar_voz.py` |
| 3 y 4. Guardar claves | En vez de `setx`, agrégalas al final de `~/.bashrc`: `echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc` (igual con `TELEGRAM_BOT_TOKEN`) y luego `source ~/.bashrc` |
| Editar archivos | En vez de `notepad`, usa `nano ~/.openjarvis/config.toml` (guardar: Ctrl+O y Enter; salir: Ctrl+X) |

> Si vuelves a ejecutar `uv sync`, se borra la voz: repite el comando `uv pip install` de arriba.
> En Chromebook, Jarvis solo funciona mientras el equipo está encendido y la terminal de Linux abierta.
