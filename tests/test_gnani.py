"""Gnani tests use mocked HTTP so they run offline. For a REAL call, see README ('Live API checks')."""
import io
import unittest
import wave
from unittest.mock import MagicMock, patch

import config
from services import gnani_stt, gnani_tts


def make_wav(seconds=0.1, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x01" * int(rate * seconds))
    return buf.getvalue()


def resp(status=200, json_body=None, content=b"", text=""):
    r = MagicMock(); r.status_code = status; r.content = content; r.text = text
    if json_body is None:
        r.json.side_effect = ValueError()
    else:
        r.json.return_value = json_body
    return r


class STTTests(unittest.TestCase):
    def setUp(self):
        patch.dict("os.environ", {"GNANI_API_KEY": "SECRET123"}).start()
        self.addCleanup(patch.stopall)

    def test_missing_key(self):
        with patch.dict("os.environ", {"GNANI_API_KEY": ""}):
            with self.assertRaisesRegex(gnani_stt.STTError, "GNANI_API_KEY"):
                gnani_stt.transcribe(b"x", "a.wav", "en-IN")

    def test_request_shape_and_success(self):
        ok = resp(200, {"success": True, "request_id": "r1", "transcript": "hello", "model": "gnani-prisma-v2.5"})
        with patch("services.gnani_stt.requests.post", return_value=ok) as post:
            out = gnani_stt.transcribe(make_wav(), "a.wav", "ta-IN")
        args, kw = post.call_args
        self.assertEqual(args[0], "https://api.vachana.ai/stt/v3")
        self.assertEqual(kw["headers"], {"X-API-Key-ID": "SECRET123"})
        self.assertEqual(kw["data"]["language_code"], "ta-IN")
        self.assertNotIn("model", kw["data"])        # omitted => Prisma v2.5
        self.assertEqual(out["transcript"], "hello")

    def test_too_long_audio_rejected_before_network(self):
        with patch("services.gnani_stt.requests.post") as post:
            with self.assertRaisesRegex(gnani_stt.STTError, "limit is 30s"):
                gnani_stt.transcribe(make_wav(31, 8000), "a.wav", "en-IN")
            post.assert_not_called()

    def test_api_errors_are_readable_and_key_is_never_leaked(self):
        bad = resp(401, {"detail": {"error_code": "INVALID_API_KEY", "message": "Unauthorized SECRET123"}})
        with patch("services.gnani_stt.requests.post", return_value=bad):
            with self.assertRaises(gnani_stt.STTError) as cm:
                gnani_stt.transcribe(make_wav(), "a.wav", "en-IN")
        self.assertIn("INVALID_API_KEY", str(cm.exception))
        self.assertNotIn("SECRET123", str(cm.exception))

    def test_rate_limit_retries_once(self):
        ok = resp(200, {"success": True, "transcript": "hi"})
        seq = [resp(429, {"detail": {"error_code": "RATE_LIMITED", "message": "busy"}}), ok]
        with patch("services.gnani_stt.requests.post", side_effect=seq), patch("services.gnani_stt.time.sleep"):
            self.assertEqual(gnani_stt.transcribe(make_wav(), "a.wav", "en-IN")["transcript"], "hi")

    def test_network_failure(self):
        import requests
        with patch("services.gnani_stt.requests.post", side_effect=requests.ConnectionError("boom")):
            with self.assertRaisesRegex(gnani_stt.STTError, "Network error"):
                gnani_stt.transcribe(make_wav(), "a.wav", "en-IN")


class TTSTests(unittest.TestCase):
    def setUp(self):
        patch.dict("os.environ", {"GNANI_API_KEY": "SECRET123"}).start()
        self.addCleanup(patch.stopall)

    def test_request_shape_and_valid_wav(self):
        wav = make_wav(0.2)
        with patch("services.gnani_tts.requests.post", return_value=resp(200, content=wav)) as post:
            out = gnani_tts.synthesize("Hello world.", "hi-IN", "Nalini")
        _, kw = post.call_args
        self.assertEqual(kw["json"]["model"], "timbre-v2.5")
        self.assertEqual(kw["json"]["voice"], "Nalini")
        self.assertEqual(kw["json"]["audio_config"]["container"], "wav")
        self.assertEqual(kw["headers"], {"X-API-Key-ID": "SECRET123"})
        self.assertEqual(out[:4], b"RIFF")

    def test_non_audio_response_is_an_error_not_fake_success(self):
        with patch("services.gnani_tts.requests.post", return_value=resp(200, content=b"<html>nope</html>")):
            with self.assertRaisesRegex(gnani_tts.TTSError, "not a valid WAV"):
                gnani_tts.synthesize("Hello.", "en-IN")

    def test_http_error(self):
        bad = resp(403, {"success": False, "error": {"type": "FORBIDDEN", "message": "no credits"}})
        with patch("services.gnani_tts.requests.post", return_value=bad):
            with self.assertRaisesRegex(gnani_tts.TTSError, "403"):
                gnani_tts.synthesize("Hello.", "en-IN")

    def test_voice_must_match_language_catalog(self):
        with self.assertRaisesRegex(gnani_tts.TTSError, "not a Timbre v2.5 voice"):
            gnani_tts.synthesize("Hi", "en-IN", "Nalini")

    def test_long_text_is_split_and_wavs_joined(self):
        text = " ".join(f"This is sentence number {i} of a long briefing." for i in range(40))
        chunks = gnani_tts.split_text(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 450 for c in chunks))
        with patch("services.gnani_tts.requests.post", return_value=resp(200, content=make_wav(0.1))) as post:
            out = gnani_tts.synthesize(text, "en-IN")
        self.assertEqual(post.call_count, len(chunks))
        with wave.open(io.BytesIO(out)) as w:
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 0.1 * len(chunks), places=1)

    def test_unbroken_long_word_does_not_loop(self):
        self.assertTrue(all(len(c) <= 450 for c in gnani_tts.split_text("x" * 1200)))

    def test_all_languages_have_voices(self):
        for code in config.LANGUAGES.values():
            self.assertIn(code, config.TTS_VOICES)


if __name__ == "__main__":
    unittest.main()
