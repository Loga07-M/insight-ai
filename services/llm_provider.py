"""Pluggable LLM provider. Add a new class + register it to switch vendors."""
import requests

import config


class LLMNotConfigured(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


class OpenAICompatible:
    """Works with OpenAI, Groq, OpenRouter, Together, Gemini's OpenAI endpoint, local servers, etc."""

    def __init__(self, s):
        self.s = s

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1500) -> str:
        r = requests.post(
            f"{self.s['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {self.s['api_key']}", "Content-Type": "application/json"},
            json={"model": self.s["model"], "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens},
            timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            raise LLMError(f"LLM API returned HTTP {r.status_code}: {config.redact(r.text[:300])}")
        try:
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            raise LLMError("LLM API returned an unexpected response format.")


class AnthropicProvider:
    def __init__(self, s):
        self.s = s

    def chat(self, messages, temperature=0.3, max_tokens=1500) -> str:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [m for m in messages if m["role"] != "system"]
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.s["api_key"], "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": self.s["model"], "system": system, "messages": rest,
                  "temperature": temperature, "max_tokens": max_tokens},
            timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            raise LLMError(f"LLM API returned HTTP {r.status_code}: {config.redact(r.text[:300])}")
        try:
            return "".join(b.get("text", "") for b in r.json()["content"]).strip()
        except Exception:
            raise LLMError("LLM API returned an unexpected response format.")


PROVIDERS = {"openai_compatible": OpenAICompatible, "anthropic": AnthropicProvider}


def llm_available() -> bool:
    return bool(config.llm_settings()["api_key"])


def get_provider():
    s = config.llm_settings()
    if not s["api_key"]:
        raise LLMNotConfigured("LLM_API_KEY is missing in your .env file. Add it to enable AI answers.")
    if s["provider"] not in PROVIDERS:
        raise LLMError(f"Unknown LLM_PROVIDER '{s['provider']}'. Use one of: {', '.join(PROVIDERS)}.")
    return PROVIDERS[s["provider"]](s)
