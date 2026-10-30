"""Jarvis notification agents — Spanish-language push messages to the phone.

Two scheduled agents that share one delivery path:

* ``jarvis_salud``: a short morning health message (sleep/activity data,
  calendar, weather and the health goals in ``USER.md``), sent to Telegram.
* ``jarvis_correos``: checks the inbox, keeps only important new emails and
  sends a summary to WhatsApp. Already-notified emails are remembered so the
  same email is never reported twice.

Both read their destinations from ``[jarvis]`` in ``config.toml``. Channel
specs use the ``"{type}:{id}"`` format of the proactive agent, e.g.
``"telegram:123456789"`` or ``"whatsapp_baileys:573001234567"``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

from openjarvis.agents._stubs import AgentContext, AgentResult, ToolUsingAgent
from openjarvis.agents.morning_digest import _format_date
from openjarvis.core.paths import get_config_dir
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Message, Role

logger = logging.getLogger(__name__)

# Reply the model gives when no email deserves a notification.
_NOTHING = "NADA"
# Cap on remembered email IDs so the state file stays small.
_MAX_SEEN_IDS = 2000
# Seconds to wait for the WhatsApp bridge to finish its handshake.
_WHATSAPP_CONNECT_TIMEOUT = 30.0

_SALUD_PROMPT = """Eres Jarvis, el asistente personal de {name}. Cada mañana le \
envías por Telegram un mensaje breve de salud.

Hoy es {date}.

Escribe el mensaje SIEMPRE en español, en un tono cálido y cercano:
- Saluda por su nombre.
- Si hay datos de sueño, actividad o salud, coméntalos en una o dos frases.
- Si hay eventos en el calendario, recuerda lo más importante del día.
- Si hay datos del clima, da un consejo práctico (hidratación, abrigo, sol).
- Termina con UN recordatorio basado en sus metas de salud.

Reglas:
- Máximo 120 palabras. Sin títulos ni markdown; como mucho 2 emojis.
- Usa SOLO los datos recibidos. Nunca inventes mediciones ni eventos.
- No des diagnósticos médicos. Si algo parece preocupante, sugiere consultar \
a un profesional de la salud.
- Si una fuente no tiene datos, omítela sin mencionarla."""

_CORREOS_PROMPT = """Eres Jarvis, el asistente personal de {name}. Revisas sus \
correos nuevos y le avisas por WhatsApp SOLO de los importantes.

Es importante: lo que pide una acción o respuesta, viene de una persona real, \
es urgente, tiene fecha límite, trata de dinero, pagos, citas médicas, trabajo \
o familia. NO es importante: boletines, publicidad, promociones, redes \
sociales, notificaciones automáticas ni correos ya leídos sin acción pendiente.

Si NINGÚN correo es importante, responde exactamente: {nothing}

Si hay importantes, escribe un mensaje en español con este formato:
📬 *Correos importantes*
• *Remitente* — de qué se trata en una frase y qué hay que hacer.

Reglas:
- Máximo 5 correos, del más al menos urgente.
- Usa SOLO la información de los correos. Nunca inventes.
- Sin saludo ni despedida: es una notificación."""


def _user_profile() -> str:
    """Return ``USER.md`` (name, health goals…) or an empty string."""
    path = get_config_dir() / "USER.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _user_name(profile: str) -> str:
    match = re.search(r"Nombre:\s*(.+)", profile)
    return match.group(1).strip() if match else "el usuario"


def _normalize_spec(spec: str) -> str:
    """Turn ``whatsapp_baileys:+57 300…`` into a WhatsApp JID spec."""
    channel_type, _, target = spec.partition(":")
    if channel_type == "whatsapp_baileys" and target and "@" not in target:
        digits = re.sub(r"\D", "", target)
        target = f"{digits}@s.whatsapp.net"
    return f"{channel_type}:{target}" if target else spec


def _has_target(spec: str) -> bool:
    """True when *spec* names both a channel type and a destination."""
    channel_type, _, target = spec.strip().partition(":")
    return bool(channel_type and target.strip())


def _text_for_speech(text: str) -> str:
    """Strip markdown markers, bullets and emojis so TTS reads only words."""
    text = re.sub(r"[*_~`#>]", "", text)
    text = re.sub(r"^\s*[•\-–]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    text = text.replace(" — ", ", ")
    return re.sub(r"[ \t]+", " ", text).strip()


def voice_note(text: str, voice_id: str = "em_alex", speed: float = 1.0) -> bytes:
    """Render *text* as an OGG/Opus voice note with the local Kokoro voice.

    Returns ``b""`` when the voice is not installed or synthesis fails, so
    callers can always fall back to text-only delivery.
    """
    spoken = _text_for_speech(text)
    if not spoken:
        return b""
    try:
        import io

        import soundfile as sf

        from openjarvis.speech.kokoro_tts import KokoroTTSBackend

        wav = KokoroTTSBackend().synthesize(spoken, voice_id=voice_id, speed=speed)
        if not wav.audio:
            return b""
        samples, rate = sf.read(io.BytesIO(wav.audio), dtype="float32")
        out = io.BytesIO()
        # Telegram and WhatsApp only render OGG/Opus as a playable voice note.
        sf.write(out, samples, rate, format="OGG", subtype="OPUS")
        return out.getvalue()
    except Exception:
        logger.warning(
            "Jarvis: voice note unavailable, sending text only", exc_info=True
        )
        return b""


def send_notification(spec: str, text: str, voice: bytes = b"") -> bool:
    """Send *text* to the ``"{type}:{id}"`` destination *spec*.

    When *voice* (OGG/Opus bytes) is given and the channel supports it, a
    voice note follows the text. Success depends on the text alone, so a
    failed voice note never causes a retry.

    Returns ``False`` (and logs why) instead of raising, so a delivery problem
    never crashes the scheduled tick.
    """
    from openjarvis.agents.proactive_agent import _build_notification_channel
    from openjarvis.channels._stubs import ChannelStatus

    if not _has_target(spec):
        logger.warning("Jarvis: no destination configured in %r", spec)
        return False
    spec = _normalize_spec(spec.strip())
    channel = _build_notification_channel(spec)
    if channel is None:
        logger.warning("Jarvis: notification channel %r unavailable", spec)
        return False
    target = spec.partition(":")[2]
    try:
        if spec.startswith("whatsapp_baileys:"):
            # The bridge reports "connected" asynchronously after connect().
            deadline = time.monotonic() + _WHATSAPP_CONNECT_TIMEOUT
            while (
                channel.status() != ChannelStatus.CONNECTED
                and time.monotonic() < deadline
            ):
                time.sleep(0.5)
        ok = channel.send(target, text)
        if ok and voice and hasattr(channel, "send_voice"):
            if not channel.send_voice(target, voice):
                logger.warning("Jarvis: voice note to %r failed", spec)
        if spec.startswith("whatsapp_baileys:"):
            # Let the bridge flush (and upload any audio) before closing.
            time.sleep(8 if voice else 3)
        return bool(ok)
    except Exception:
        logger.warning("Jarvis: failed to send to %r", spec, exc_info=True)
        return False
    finally:
        try:
            channel.disconnect()
        except Exception:  # noqa: BLE001
            pass


class _JarvisNotifier(ToolUsingAgent):
    """Shared collect → write → send flow for the Jarvis agents."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        cfg = kwargs.pop("jarvis_config", None)
        super().__init__(*args, **kwargs)
        if cfg is None:
            from openjarvis.core.config import load_config

            cfg = load_config().jarvis
        self._cfg = cfg

    def _write(self, system_prompt: str, data: str) -> str:
        messages = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(
                role=Role.USER,
                content=f"<datos>\n{data}\n</datos>",
            ),
        ]
        result = self._generate(messages)
        return self._strip_think_tags(result.get("content", "")).strip()

    def _voice(self, text: str) -> bytes:
        if not self._cfg.voice_notes:
            return b""
        return voice_note(text, voice_id=self._cfg.voice_id)

    def _finish(
        self, content: str, *, sent: bool, destination: str, **meta: Any
    ) -> AgentResult:
        meta.update({"sent": sent, "destination": destination})
        self._emit_turn_end(turns=1)
        return AgentResult(content=content, turns=1, metadata=meta)


@AgentRegistry.register("jarvis_salud")
class JarvisSaludAgent(_JarvisNotifier):
    """Morning health message, delivered to ``[jarvis] health_channel``."""

    agent_id = "jarvis_salud"

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        self._emit_turn_start(input)
        destination = self._cfg.health_channel
        if not _has_target(destination):
            return self._finish(
                "Configura [jarvis] health_channel para recibir el mensaje.",
                sent=False,
                destination=destination,
            )
        from openjarvis.tools.digest_collect import DigestCollectTool

        collected = DigestCollectTool().execute(
            sources=list(self._cfg.health_sources), hours_back=24
        )
        profile = _user_profile()
        data = f"{collected.content}\n\n=== PERFIL Y METAS DE SALUD ===\n{profile}"
        prompt = _SALUD_PROMPT.format(
            name=_user_name(profile), date=_format_date(datetime.now(), "es")
        )
        text = self._write(prompt, data)
        sent = bool(text) and send_notification(
            destination, text, voice=self._voice(text)
        )
        return self._finish(text, sent=sent, destination=destination)


@AgentRegistry.register("jarvis_correos")
class JarvisCorreosAgent(_JarvisNotifier):
    """Important-email alerts, delivered to ``[jarvis] email_channel``."""

    agent_id = "jarvis_correos"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._state_path = Path(
            kwargs.pop("state_path", "") or get_config_dir() / "jarvis_correos.json"
        )
        super().__init__(*args, **kwargs)

    def _load_seen(self) -> List[str]:
        try:
            return list(json.loads(self._state_path.read_text("utf-8"))["seen"])
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def _save_seen(self, seen: List[str]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"seen": seen[-_MAX_SEEN_IDS:]}
        self._state_path.write_text(json.dumps(payload), encoding="utf-8")

    def _new_emails(self, seen: set) -> List[Any]:
        """Fetch emails from the configured connectors, skipping *seen* IDs."""
        import openjarvis.connectors  # noqa: F401  trigger registration
        from openjarvis.core.registry import ConnectorRegistry

        since = datetime.now() - timedelta(hours=self._cfg.email_hours_back)
        docs: List[Any] = []
        for source in self._cfg.email_sources:
            if not ConnectorRegistry.contains(source):
                logger.warning("Jarvis: connector %r not available", source)
                continue
            try:
                connector = ConnectorRegistry.get(source)()
                if not connector.is_connected():
                    logger.warning("Jarvis: connector %r not connected", source)
                    continue
                for doc in connector.sync(since=since):
                    if doc.doc_id not in seen:
                        docs.append(doc)
                    if len(docs) >= 25:
                        break
            except Exception:
                logger.warning("Jarvis: failed to read %r", source, exc_info=True)
        return docs

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        self._emit_turn_start(input)
        from openjarvis.tools.digest_collect import _format_doc

        destination = self._cfg.email_channel
        if not _has_target(destination):
            # Skip the inbox read and the model call until a destination exists.
            return self._finish(
                "Configura [jarvis] email_channel para recibir avisos.",
                sent=False,
                destination=destination,
                new=0,
            )
        seen = self._load_seen()
        emails = self._new_emails(set(seen))
        if not emails:
            return self._finish(
                "Sin correos nuevos.", sent=False, destination=destination, new=0
            )

        data = "\n".join(
            f"{_format_doc(doc.source, doc)}\n{(doc.content or '')[:500]}"
            for doc in emails
        )
        prompt = _CORREOS_PROMPT.format(
            name=_user_name(_user_profile()), nothing=_NOTHING
        )
        text = self._write(prompt, data)

        sent = False
        important = bool(text) and text.strip(" .") != _NOTHING
        if important:
            sent = send_notification(destination, text, voice=self._voice(text))
        # Remember the batch unless an alert was due but could not be sent,
        # so a delivery failure is retried on the next tick.
        if sent or not important:
            self._save_seen(seen + [doc.doc_id for doc in emails])
        content = text if important else "Ningún correo importante."
        return self._finish(
            content, sent=sent, destination=destination, new=len(emails)
        )


__all__ = ["JarvisCorreosAgent", "JarvisSaludAgent", "send_notification", "voice_note"]
