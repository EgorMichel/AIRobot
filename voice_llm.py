"""
Voice-controlled LLM client using SpeechRecognition + gTTS.

Features
- Hotword-free push-to-talk: press Enter to record, Ctrl+C to quit.
- Speech-to-text via Google Web Speech API (free tier used by speech_recognition).
- Sends text to your LLM HTTP API (set URL/KEY via environment or .env).
- Text-to-speech of the model reply via gTTS and playsound.

Environment variables (create a .env file or set in shell):
- LLM_API_URL: full endpoint URL, e.g. https://api.example.com/v1/chat
- LLM_API_KEY: bearer/token key if required (omit if public)
- LLM_MODEL: optional model name sent in the payload

Payload shape is adjustable in build_llm_payload(). Edit as needed for your API.
"""

import os
import tempfile
import uuid
from typing import Optional
import requests
from dotenv import load_dotenv
import speech_recognition as sr
from gtts import gTTS
from playsound3 import playsound

load_dotenv()

LLM_API_URL_RAW = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o")
MIC_DEVICE_INDEX_RAW: Optional[str] = os.getenv("MIC_DEVICE_INDEX")
try:
    MIC_DEVICE_INDEX: Optional[int] = int(MIC_DEVICE_INDEX_RAW) if MIC_DEVICE_INDEX_RAW is not None else None
except ValueError:
    MIC_DEVICE_INDEX = None


def resolve_llm_url(base_url: Optional[str]) -> str:
    if not base_url:
        raise RuntimeError("LLM_API_URL is not set. Define it in .env or environment.")
    url = base_url.rstrip("/")
    if url.endswith("/api") or url.endswith("/api/v1") or url.endswith("/v1"):
        url = url + "/chat/completions"
    return url


LLM_API_URL = resolve_llm_url(LLM_API_URL_RAW)
print(f"[config] LLM endpoint: {LLM_API_URL}")
print(f"[config] LLM model: {LLM_MODEL or '(not set)'}")

recognizer = sr.Recognizer()
try:
    mic = sr.Microphone(device_index=MIC_DEVICE_INDEX)
except OSError as exc:
    mic = None
    print(f"[warn] Cannot open microphone (device_index={MIC_DEVICE_INDEX}). Set MIC_DEVICE_INDEX env or check audio devices. Error: {exc}")


def build_llm_payload(user_text: str) -> dict:
    """Adjust this to match your LLM API contract."""
    payload = {
        "model": LLM_MODEL or None,
        "messages": [
            {"role": "user", "content": user_text},
        ],
    }
    # Remove None fields to avoid sending empty model
    return {k: v for k, v in payload.items() if v}


def call_llm(user_text: str) -> str:
    if not LLM_API_URL:
        raise RuntimeError("LLM_API_URL is not set. Define it in .env or environment.")

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"  # adjust scheme if needed

    resp = requests.post(LLM_API_URL, json=build_llm_payload(user_text), headers=headers, timeout=60)
    try:
        resp.raise_for_status()
    except requests.HTTPError as http_err:
        body = None
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"LLM API error: {http_err}; response: {body}") from http_err
    data = resp.json()

    # Adjust this extraction to match your API's response shape
    # Expected: {choices: [{message: {content: "..."}}]}
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected LLM response format: {data}") from e


def tts_and_play(text: str) -> None:
    tts = gTTS(text)
    tmp_path = os.path.join(tempfile.gettempdir(), f"llm_reply_{uuid.uuid4().hex}.mp3")
    tts.save(tmp_path)
    playsound(tmp_path)
    try:
        os.remove(tmp_path)
    except OSError:
        pass


def listen_once() -> str:
    if mic is None:
        raise RuntimeError(
            "Microphone is not available. Set MIC_DEVICE_INDEX or check audio devices and permissions."
        )
    with mic as source:
        print("[listening] Speak now...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)
    print("[processing] Converting speech to text...")
    try:
        text = recognizer.recognize_google(audio, language="ru-RU")  # change language if needed
        print(f"[you] {text}")
        return text
    except sr.UnknownValueError:
        print("[warn] Could not understand audio.")
        return ""
    except sr.RequestError as exc:
        raise RuntimeError(f"SpeechRecognition API error: {exc}")


def main():
    print("Voice LLM client. Press Enter to talk; Ctrl+C to exit.")
    print("Ensure microphone access is allowed.")

    while True:
        try:
            input("\nPress Enter and start speaking...")
            user_text = listen_once()
            if not user_text:
                continue
            reply = call_llm(user_text)
            print(f"[llm] {reply}")
            tts_and_play(reply)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as exc:
            print(f"[error] {exc}")


if __name__ == "__main__":
    main()

