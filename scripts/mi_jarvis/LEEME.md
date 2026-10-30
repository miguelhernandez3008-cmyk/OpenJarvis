# Mi Jarvis en español: guía de instalación (Windows)

Esta configuración deja a Jarvis:

- **Respondiendo siempre en español**, en el chat y en el resumen de la mañana (también por voz).
- **Conectado a Telegram**, para hablarle desde el celular.
- **Usando Claude en la nube**, así no necesitas una computadora potente.

---

## 1. Instala los programas base (una sola vez)

Abre **PowerShell** y ejecuta:

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
```

Cierra PowerShell y ábrelo de nuevo para que reconozca los programas.

## 2. Descarga tu copia del proyecto

```powershell
cd $HOME
git clone -b personalizacion-es https://github.com/miguelhernandez3008-cmyk/OpenJarvis.git
cd OpenJarvis
uv sync --extra inference-cloud --extra channel-telegram --extra voice --extra server
```

La primera vez tarda unos minutos.

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

4. **Importante, por seguridad:** busca **@userinfobot** en Telegram y envíale cualquier mensaje. Te responde con tu **Id** (un número). Así el bot solo te responde a ti.

Cierra PowerShell y ábrelo de nuevo para que tome las claves.

## 5. Instala la configuración

```powershell
cd $HOME\OpenJarvis
uv run python scripts/mi_jarvis/instalar.py
```

Luego abre el archivo de configuración:

```powershell
notepad $HOME\.openjarvis\config.toml
```

y edita dos cosas:

- `allowed_chat_ids = ""`: pon tu Id de Telegram entre las comillas, por ejemplo `allowed_chat_ids = "123456789"`.
- `timezone = "America/Bogota"`: cámbialo a tu zona horaria (por ejemplo `America/Mexico_City` o `Europe/Madrid`).

## 6. ¡A usarlo!

```powershell
uv run jarvis doctor     # revisa que todo esté bien
uv run jarvis chat       # chatea en la terminal
uv run jarvis gui        # interfaz gráfica en el navegador (requiere Node.js 22+)
uv run jarvis serve      # deja el bot de Telegram escuchando
```

Con `jarvis serve` corriendo, abre tu bot en Telegram y escríbele "hola".

### Resumen de la mañana

```powershell
uv run jarvis connect gdrive   # conecta Gmail, Calendar y Tasks (una sola vez)
uv run jarvis digest --fresh   # genera y reproduce el resumen
```

> **Voz en español:** la voz local (Kokoro) necesita **espeak-ng**. Instálalo con
> `winget install --id eSpeak-NG.eSpeak-NG -e`. Si no te funciona, puedes generar
> solo el texto con `uv run jarvis digest --fresh --text-only`.

---

## Personalizar

| Quiero cambiar… | Archivo |
|---|---|
| La personalidad de Jarvis en el chat | `~/.openjarvis/SOUL.md` |
| Lo que Jarvis sabe de mí | `~/.openjarvis/USER.md` |
| El modelo, las herramientas o el horario del resumen | `~/.openjarvis/config.toml` |
| La personalidad del resumen de la mañana | `~/.openjarvis/prompts/personas/jarvis_es.md` |

Los originales están en esta carpeta (`scripts/mi_jarvis/`) y en `configs/openjarvis/examples/mi-jarvis-es.toml`.
Si vuelves a ejecutar `instalar.py`, antes de reemplazar tus archivos guarda una copia de respaldo.
