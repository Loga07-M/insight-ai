"""Gnani Timbre v2.5 text-to-speech (REST)."""
import io
import re
import time
import wave

import requests

import config


class TTSError(RuntimeError):
    pass


MAX_CHUNK_BYTES = 25 * 1024 * 1024
MAX_TOTAL_AUDIO_BYTES = 100 * 1024 * 1024
MAX_CHUNKS = 40
MAX_WAV_BYTES = 0xFFFFFFFF - 36


def split_text(text: str, max_chars: int = 450) -> list[str]:
    """Split text into short sentence-based chunks."""
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?।])\s+", text)

    chunks = []
    cur = ""

    for s in sentences:
        while len(s) > max_chars:
            cut = s.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars

            chunks.append(s[:cut].strip())
            s = s[cut:].strip()

        if len(cur) + len(s) + 1 > max_chars and cur:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()

    if cur:
        chunks.append(cur)

    return [c for c in chunks if c]


def _read_wav(audio: bytes):
    """Read and validate WAV audio."""
    if not audio or len(audio) > MAX_CHUNK_BYTES:
        raise TTSError("Audio chunk is empty or exceeds the 25 MB limit.")

    try:
        with wave.open(io.BytesIO(audio), "rb") as src:
            channels = src.getnchannels()
            sample_width = src.getsampwidth()
            sample_rate = src.getframerate()

            if channels < 1 or sample_width < 1 or sample_rate < 1:
                raise TTSError("Invalid WAV audio format.")

            if src.getcomptype() != "NONE":
                raise TTSError("Unsupported compressed WAV audio.")

            frames = src.readframes(src.getnframes())

        frame_size = channels * sample_width

        if not frames or len(frames) % frame_size != 0:
            raise TTSError("TTS returned invalid or incomplete audio frames.")

        return (channels, sample_width, sample_rate), frames

    except TTSError:
        raise
    except (wave.Error, EOFError, OSError) as exc:
        raise TTSError(f"Could not read WAV audio: {exc}") from exc


def _write_wav(params, frames: bytes) -> bytes:
    """Create a WAV file with a correct header."""
    if len(frames) > MAX_WAV_BYTES:
        raise TTSError("Combined audio exceeds the WAV file size limit.")

    out = io.BytesIO()

    try:
        with wave.open(out, "wb") as dst:
            dst.setnchannels(params[0])
            dst.setsampwidth(params[1])
            dst.setframerate(params[2])
            dst.writeframes(frames)

        return out.getvalue()

    except (wave.Error, EOFError, OSError, OverflowError) as exc:
        raise TTSError(f"Could not create WAV audio: {exc}") from exc


def _normalize_wav_header(audio: bytes) -> bytes:
    """Rebuild WAV metadata using actual audio frames."""
    params, frames = _read_wav(audio)
    return _write_wav(params, frames)


def join_wavs(parts: list[bytes]) -> bytes:
    """Safely join WAV chunks with matching formats."""
    if not parts:
        raise TTSError("No audio chunks were received.")

    if len(parts) > MAX_CHUNKS:
        raise TTSError("Too many audio chunks to combine.")

    params = None
    combined = bytearray()

    for part in parts:
        current_params, frames = _read_wav(part)

        if params is None:
            params = current_params
        elif current_params != params:
            raise TTSError(
                "Audio chunks have different formats and cannot be joined."
            )

        if len(combined) + len(frames) > MAX_TOTAL_AUDIO_BYTES:
            raise TTSError(
                "Combined audio exceeds the 100 MB safety limit."
            )

        combined.extend(frames)

    return _write_wav(params, bytes(combined))


def _is_wav(b: bytes) -> bool:
    return (
        len(b) > 1000
        and b[:4] == b"RIFF"
        and b[8:12] == b"WAVE"
    )


def _synth_one(
    text: str,
    voice: str,
    language: str,
    speed: float,
    key: str
) -> bytes:

    payload = {
        "text": text,
        "voice": voice,
        "model": config.GNANI_TTS_MODEL,
        "language": language,
        "speed": speed,
        "audio_config": {
            "sample_rate": 24000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    for attempt in range(3):
        try:
            r = requests.post(
                config.GNANI_TTS_URL,
                json=payload,
                headers={"X-API-Key-ID": key},
                timeout=config.HTTP_TIMEOUT,
            )

        except requests.RequestException as exc:
            raise TTSError(
                f"Network error contacting Gnani TTS: {type(exc).__name__}"
            ) from exc

        if r.status_code in (429, 500, 503) and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue

        if r.status_code != 200:
            try:
                b = r.json()
                msg = (
                    b["error"].get("message")
                    if isinstance(b.get("error"), dict)
                    else str(b.get("detail", b))[:200]
                )
            except Exception:
                msg = r.text[:200]

            hint = (
                " (check GNANI_API_KEY and TTS access/credits)"
                if r.status_code in (401, 402, 403)
                else ""
            )

            raise TTSError(
                config.redact(
                    f"Gnani TTS HTTP {r.status_code}: {msg}{hint}"
                )
            )

        if not _is_wav(r.content):
            raise TTSError(
                "Gnani TTS returned data that is not a valid WAV file."
            )

        return _normalize_wav_header(r.content)

    raise TTSError("Gnani TTS is temporarily unavailable.")


def synthesize(
    text: str,
    language: str = "en-IN",
    voice: str | None = None,
    speed: float = 1.0
) -> bytes:
    """Convert text into WAV audio."""

    key = config.gnani_key()

    if not key:
        raise TTSError("GNANI_API_KEY is missing in your .env file.")

    if language not in config.TTS_VOICES:
        raise TTSError(f"Unsupported language: {language}")

    voice = voice or config.TTS_VOICES[language][0]

    if voice not in config.TTS_VOICES[language]:
        raise TTSError(
            f"Voice '{voice}' is not a Timbre v2.5 voice for {language}."
        )

    chunks = split_text(text)

    if not chunks:
        raise TTSError("There is no text to convert to speech.")

    if len(chunks) > MAX_CHUNKS:
        raise TTSError("Text is too long for one audio generation request.")

    audio_parts = []

    for chunk in chunks:
        audio_parts.append(
            _synth_one(chunk, voice, language, speed, key)
        )

    return join_wavs(audio_parts)