"""Voice output (TTS) implementation."""
from __future__ import annotations
import os
import tempfile
import uuid
from abc import ABC, abstractmethod

from gtts import gTTS
from playsound3 import playsound


class IVoiceOutput(ABC):
    """Abstract interface for a voice output sink (TTS)."""

    @abstractmethod
    async def speak(self, text: str):
        """Synthesizes and speaks the given text."""
        raise NotImplementedError


class GTTSOutput(IVoiceOutput):
    """
    IVoiceOutput implementation using Google Text-to-Speech (gTTS) and playsound.
    """

    async def speak(self, text: str, lang: str = "ru", tld: str = "com"):
        """
        Generates an MP3 file from the text, plays it, and then deletes it.
        """
        if not text:
            print("[warn] TTS received empty text, skipping.")
            return

        print(f"[tts] Saying: {text}")
        try:
            tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
            # Use a temporary file to store the speech
            tmp_path = os.path.join(tempfile.gettempdir(), f"mcp_reply_{uuid.uuid4().hex}.mp3")
            tts.save(tmp_path)
            playsound(tmp_path)
        except Exception as e:
            print(f"[error] Failed to play TTS audio: {e}")
        finally:
            # Clean up the temporary file
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError as e:
                    print(f"[warn] Failed to remove temporary TTS file {tmp_path}: {e}")


class ConsoleOutput(IVoiceOutput):
    """
    A dummy IVoiceOutput implementation that prints text to the console instead of speaking.
    Useful for debugging or running in environments without audio output.
    """
    async def speak(self, text: str):
        """Prints the text to the console with a [tts-dummy] prefix."""
        print(f"[tts-dummy] {text}")
