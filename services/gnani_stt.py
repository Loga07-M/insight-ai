"""Gnani Prisma v2.5 speech-to-text (REST). Server-side only; key never leaves this process."""
import io
import time
import wave

import requests

import config


class STTError(RuntimeError):
    pass


def _audio_seconds(data: bytes, filename: str) -> float | None:
    if filename.lower().endswith(".wav"):
        try:
            with wave.open(io.BytesIO(data)) as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return None
    return None


def _error_message(resp) -> str:
    try:
        body = resp.json()
    except Exception:
        return f"HTTP {resp.status_code}"
    if isinstance(body.get("error"), dict):
        return f"{body['error'].get('type', 'ERROR')}: {body['error'].get('message', '')}"
    detail = body.get("detail")
    if isinstance(detail, dict):
        return f"{detail.get('error_code', 'ERROR')}: {detail.get('message', '')}"
    return f"HTTP {resp.status_code}: {str(body)[:200]}"


def transcribe(audio_bytes: bytes, filename: str, language_code: str, enable_itn: bool = True) -> dict:
    """Returns {'transcript','request_id','model'}. Raises STTError with a readable message."""
    key = config.gnani_key()
    if not key:
        raise STTError("GNANI_API_KEY is missing in your .env file.")
    if language_code not in config.LANGUAGES.values():
        raise STTError(f"Unsupported language code: {language_code}")
    if not audio_bytes:
        raise STTError("The audio is empty. Please record again.")
    secs = _audio_seconds(audio_bytes, filename)
    if secs is not None and secs > config.STT_MAX_SECONDS:
        raise STTError(f"Audio is {secs:.0f}s long; the limit is {config.STT_MAX_SECONDS}s. Please record a shorter question.")

    data = {"language_code": language_code}          # model omitted => Prisma v2.5 (default)
    if enable_itn:
        data["format"] = "transcribe"                # numbers/dates in written form
    last = ""
    for attempt in range(2):                         # one retry: account may allow 1 active request
        try:
            r = requests.post(config.GNANI_STT_URL, headers={"X-API-Key-ID": key},
                              files={"audio_file": (filename, audio_bytes)}, data=data,
                              timeout=config.HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise STTError(f"Network error contacting Gnani STT: {config.redact(type(exc).__name__)}")
        if r.status_code == 429 and attempt == 0:
            time.sleep(2)
            continue
        if r.status_code != 200:
            last = _error_message(r)
            if r.status_code in (401, 403):
                last += " (check GNANI_API_KEY and that it has STT access/credits)"
            raise STTError(config.redact(last))
        try:
            body = r.json()
        except ValueError:
            raise STTError("Gnani STT returned a non-JSON response.")
        if not body.get("success", False):
            raise STTError(config.redact(_error_message(r)))
        return {"transcript": (body.get("transcript") or "").strip(),
                "request_id": body.get("request_id", ""), "model": body.get("model", "")}
    raise STTError(config.redact(last or "Gnani STT is busy (rate limited). Try again shortly."))
