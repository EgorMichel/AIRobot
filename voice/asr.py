"""Voice input implementation using speech_recognition library."""
from __future__ import annotations
import os
from abc import ABC, abstractmethod
from typing import Optional
from core.types import TextCallback

import speech_recognition as sr


class IVoiceInput(ABC):
    """Abstract interface for a voice input source (ASR)."""

    @abstractmethod
    async def start(self):
        """Starts listening. This can be a long-running loop or event-based."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self):
        """Stops listening."""
        raise NotImplementedError

    @abstractmethod
    def on_text(self, callback: TextCallback):
        """Registers a callback to be invoked when new text is transcribed."""
        raise NotImplementedError

    @abstractmethod
    async def listen_once(self) -> str:
        """Listens for a single utterance and returns the transcribed text."""
        raise NotImplementedError


class SpeechRecognitionInput(IVoiceInput):
    """
    IVoiceInput implementation using the SpeechRecognition library.
    It captures audio from a microphone and uses Google Web Speech API for transcription.
    """

    def __init__(self, mic_device_index: Optional[int] = None, language: str = "ru-RU"):
        self.mic_device_index = mic_device_index
        self.language = language
        self.recognizer = sr.Recognizer()
        self.mic = self._get_mic()
        self._callback: Optional[TextCallback] = None

    def _get_mic(self) -> Optional[sr.Microphone]:
        """Initializes the microphone, handling potential errors."""
        try:
            return sr.Microphone(device_index=self.mic_device_index)
        except OSError as exc:
            print(f"[warn] Cannot open microphone (device_index={self.mic_device_index}). Set MIC_DEVICE_INDEX env or check audio devices. Error: {exc}")
            return None
        except Exception as exc:
            print(f"[warn] An unexpected error occurred with the microphone: {exc}")
            return None

    def on_text(self, callback: TextCallback):
        self._callback = callback

    async def listen_once(self) -> str:
        """
        Listens for a single phrase, transcribes it, and returns the text.
        Invokes the callback if registered.
        """
        if self.mic is None:
            msg = "Microphone is not available. Set MIC_DEVICE_INDEX or check audio devices and permissions."
            print(f"[error] {msg}")
            return ""
        
        with self.mic as source:
            print("[listening] Speak now...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                print("[warn] No speech detected within the timeout period.")
                return ""

        print("[processing] Converting speech to text...")
        try:
            text = self.recognizer.recognize_google(audio, language=self.language)
            print(f"[you] {text}")
            if self._callback:
                self._callback(text)
            return text
        except sr.UnknownValueError:
            print("[warn] Could not understand audio.")
            return ""
        except sr.RequestError as exc:
            print(f"[error] SpeechRecognition API error: {exc}")
            raise RuntimeError(f"SpeechRecognition API error: {exc}") from exc

    async def start(self):
        """Starts a loop that continuously listens for a single utterance."""
        print("Starting continuous listening loop. Press Ctrl+C to stop.")
        while True:
            try:
                await self.listen_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[error] Unhandled exception in listening loop: {e}")


    async def stop(self):
        """Stops the listening loop (in this implementation, the user must Ctrl+C)."""
        print("Stopping voice input. Please use Ctrl+C to exit the listening loop.")
