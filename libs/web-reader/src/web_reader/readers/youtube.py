"""
YouTube reader — fetch video transcripts without a browser.

Tries yt-dlp subtitles first, then optional audio transcription fallback.
"""

import html
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from openai import OpenAI
import yt_dlp

from ..models import ReadResult

logger = logging.getLogger(__name__)


def _build_transcription_client() -> tuple[OpenAI, str]:
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("No GROQ_API_KEY found. Please set GROQ_API_KEY in your environment or .env file.")

    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_api_key)
    return client, "whisper-large-v3"


def _extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    parsed = urlparse(url)

    # youtu.be/VIDEO_ID
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/").split("/")[0]

    # youtube.com/watch?v=VIDEO_ID
    if "youtube.com" in parsed.netloc:
        if "v" in parse_qs(parsed.query):
            return parse_qs(parsed.query)["v"][0]
        # youtube.com/shorts/VIDEO_ID
        if "/shorts/" in parsed.path:
            return parsed.path.split("/shorts/")[1].split("/")[0]

    return None


def _cookiefile_path() -> str | None:
    # Only use explicit path from environment variable
    env_path = os.environ.get("YOUTUBE_COOKIES")
    if env_path and os.path.exists(env_path):
        return env_path

    return None


def _build_markdown(video_id: str, text: str, language: str) -> str:
    return (
        f"VIDEO_ID: {video_id}\n"
        f"VIDEO_URL: https://www.youtube.com/watch?v={video_id}\n"
        f"LANG: {language}\n"
        f"\nTRANSCRIPT:\n{text}"
    )


def _build_result(
    video_id: str,
    text: str,
    language: str,
    method: str,
    snippet_count: int | None = None,
) -> ReadResult:
    raw: dict[str, object] = {
        "video_id": video_id,
        "language": language,
        "method": method,
    }
    if snippet_count is not None:
        raw["snippet_count"] = snippet_count

    return ReadResult(
        url=f"https://www.youtube.com/watch?v={video_id}",
        text=_build_markdown(video_id, text, language),
        title=f"YouTube Video {video_id}",
        source_type="youtube",
        language=language,
        raw=raw,
    )


def _vtt_to_text(content: str) -> str:
    lines: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)

    return "\n".join(lines)


def _subtitle_language_rank(path: Path, languages: list[str]) -> tuple[int, str]:
    filename = path.name.lower()
    for index, language in enumerate(languages):
        needle = f".{language.lower()}."
        if needle in filename or filename.endswith(f".{language.lower()}.vtt"):
            return index, filename
    return len(languages), filename


def _download_ytdlp_subtitles(url: str, video_id: str, languages: list[str]) -> tuple[str, str] | None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": languages,
            "subtitlesformat": "vtt",
            "outtmpl": output_template,
            "cookiefile": _cookiefile_path(),
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        subtitle_files = sorted(
            Path(temp_dir).glob(f"{video_id}*.vtt"),
            key=lambda item: _subtitle_language_rank(item, languages),
        )

        for subtitle_file in subtitle_files:
            text = _vtt_to_text(subtitle_file.read_text(encoding="utf-8", errors="ignore"))
            if not text.strip():
                continue

            language = "unknown"
            stem_parts = subtitle_file.stem.split(".")
            if len(stem_parts) >= 2:
                language = stem_parts[-1]

            return text, language

    return None


async def read_youtube(
    url: str,
    languages: Optional[list[str]] = None,
    use_audio_fallback: bool = True,
) -> ReadResult:
    """
    Fetch YouTube video transcript.

    Args:
        url: YouTube video URL.
        languages: Preferred languages, e.g. ["en", "zh"]. Defaults to ["en", "zh"].
        use_audio_fallback: Whether to fallback to AI transcription if captions fail. Defaults to True.

    Requires: pip install web-reader[youtube]
    """
    if languages is None:
        languages = ["en", "zh"]

    video_id = _extract_video_id(url)
    if not video_id:
        return ReadResult.fail(url, "Could not extract video ID from URL", source_type="youtube")

    subtitle_error: Exception | None = None

    # Strategy 1: yt-dlp subtitle tracks (manual or auto-generated)
    try:
        subtitle_result = _download_ytdlp_subtitles(url, video_id, languages)
        if subtitle_result:
            text, language = subtitle_result
            return _build_result(
                video_id,
                text,
                language,
                method="yt-dlp-subs",
                snippet_count=len(text.splitlines()),
            )
    except Exception as e:
        subtitle_error = e
        logger.info(f"yt-dlp subtitles fetch failed for {video_id}: {e}")

    if not use_audio_fallback:
        error = str(subtitle_error) if subtitle_error else "No subtitles available via yt-dlp"
        return ReadResult.fail(url, f"Transcript unavailable: {error}", source_type="youtube")

    # Strategy 2: AI transcription fallback
    try:
        logger.info(f"Attempting AI transcription fallback for {video_id}...")
        transcript_text = await transcribe_youtube(url)
        return _build_result(
            video_id,
            transcript_text,
            "ai-transcribed",
            method="ai-whisper",
        )
    except Exception as e:
        return ReadResult.fail(url, f"All strategies failed: {e}", source_type="youtube")


async def transcribe_youtube(url: str) -> str:
    """Download audio and transcribe it using Whisper."""
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")

    # 1. Setup temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path_tmpl = os.path.join(temp_dir, "audio.%(ext)s")
        
        ydl_opts = {
            "format": "worstaudio/worst",
            "outtmpl": audio_path_tmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "cookiefile": _cookiefile_path(),
        }

        # 2. Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the actual file
        downloaded_files = os.listdir(temp_dir)
        if not downloaded_files:
            raise FileNotFoundError("Audio file was not downloaded successfully.")
        
        audio_path = os.path.join(temp_dir, downloaded_files[0])

        # 3. AI Transcription
        client, model = _build_transcription_client()

        with open(audio_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                model=model,
                file=file,
                response_format="text",
                prompt="Transcribe the audio exactly as spoken. Original language. No translation. technical Chinese/English.",
            )
        
        return str(transcription)
