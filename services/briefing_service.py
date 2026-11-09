"""Daily briefing: select stories, generate a script and create audio."""

import config
from services import gnani_tts
from services.llm_provider import get_provider


LANG_NAME = {v: k for k, v in config.LANGUAGES.items()}

BRIEFING_SYSTEM = """You are a professional news presenter writing a spoken briefing script for one listener.

Rules:
- Use ONLY the provided stories.
- Never invent facts, numbers or quotes.
- Open with a short greeting.
- Connect stories with natural transitions.
- Explain briefly why each story matters.
- End with a one-line sign-off.
- Spoken style, no bullet points, markdown, URLs or emojis.
- Spell out numbers as words where natural.
- Total length about 200 to 280 words.
- Write the entire script in {language}.
- If the language is not English, use its native script.
"""


def select_stories(
    articles: list[dict],
    interests: list[str],
    max_items: int = 5
) -> list[dict]:

    """Select stories across different interests."""

    if not interests:
        return []

    by_topic = {
        topic: [
            article for article in articles
            if article.get("topic") == topic
        ]
        for topic in interests
    }

    picks = []
    i = 0

    while len(picks) < max_items and any(by_topic.values()):
        topic = interests[i % len(interests)]

        if by_topic.get(topic):
            picks.append(by_topic[topic].pop(0))

        i += 1

        if i > 200:
            break

    return picks


def write_script(
    stories: list[dict],
    language_code: str
) -> str:

    """Generate and validate the briefing script."""

    if not stories:
        raise ValueError(
            "No news stories are available for your selected interests."
        )

    lang = LANG_NAME.get(language_code, "English")

    listing = "\n".join(
        f"{n}. [{s.get('topic', 'News')}] "
        f"{s.get('title', 'Untitled')} "
        f"({s.get('source', 'Unknown source')}). "
        f"{s.get('summary', '')[:350]}"
        for n, s in enumerate(stories, 1)
    )

    response = get_provider().chat(
        [
            {
                "role": "system",
                "content": BRIEFING_SYSTEM.format(language=lang)
            },
            {
                "role": "user",
                "content": f"Stories:\n{listing}"
            }
        ],
        temperature=0.4,
        max_tokens=900
    )

    if not isinstance(response, str):
        raise ValueError(
            "The AI provider did not return a valid briefing script."
        )

    script = response.strip()

    if not script:
        raise ValueError(
            "The AI provider returned an empty script. "
            "Please check your LLM provider connection and try again."
        )

    return script


def make_briefing(
    articles: list[dict],
    interests: list[str],
    language_code: str,
    voice: str | None
) -> dict:

    """Generate briefing text and audio."""

    stories = select_stories(articles, interests)

    script = write_script(stories, language_code)

    if not script.strip():
        raise ValueError(
            "Briefing script is empty. Audio cannot be generated."
        )

    try:
        audio = gnani_tts.synthesize(
            script,
            language_code,
            voice
        )

        audio_error = ""

    except gnani_tts.TTSError as exc:
        audio = None
        audio_error = str(exc)

    return {
        "script": script,
        "stories": stories,
        "audio": audio,
        "audio_error": audio_error,
        "language": language_code,
        "voice": voice
    }