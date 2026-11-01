"""Transcribe incoming private Telegram voice notes and round videos."""
import asyncio
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
import librosa
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor
from telethon import TelegramClient, events
from telethon.utils import get_display_name


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
if not api_id or not api_hash:
    raise SystemExit(".env faylida TELEGRAM_API_ID va TELEGRAM_API_HASH bo'lishi kerak.")

output_mode = os.getenv("VOICE_OUTPUT", "chat").strip().lower()
if output_mode not in {"chat", "me"}:
    raise SystemExit("VOICE_OUTPUT qiymati 'chat' yoki 'me' bo'lishi kerak.")
try:
    max_seconds = int(os.getenv("VOICE_MAX_SECONDS", "600"))
    if max_seconds < 1:
        raise ValueError
except ValueError:
    raise SystemExit("VOICE_MAX_SECONDS musbat butun son bo'lishi kerak.")

# A separate session avoids colliding with the project's existing Telethon session.
client = TelegramClient(str(ROOT / "python" / "voice_transcriber_session"), int(api_id), api_hash)
model_id = os.getenv("UZBEK_STT_MODEL", "Kotib/uzbek_stt_v1")
processor = None
asr_model = None


def transcribe(path: str) -> str:
    global processor, asr_model
    if processor is None or asr_model is None:
        print(f"O'zbekcha model yuklanmoqda: {model_id} (birinchi marta ~3 GB)...")
        processor = WhisperProcessor.from_pretrained(model_id)
        asr_model = WhisperForConditionalGeneration.from_pretrained(model_id).eval()

    audio, sample_rate = librosa.load(path, sr=16000, mono=True)
    features = processor(audio, sampling_rate=sample_rate, return_tensors="pt").input_features
    with torch.inference_mode():
        token_ids = asr_model.generate(features, language="uz", task="transcribe")
    return processor.batch_decode(token_ids, skip_special_tokens=True)[0].strip()


@client.on(events.NewMessage(incoming=True))
async def handle_voice(event):
    message = event.message
    if not event.is_private or not (message.voice or message.video_note):
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return
    duration = int(getattr(message.file, "duration", 0) or 0)
    if duration > max_seconds:
        print(f"O'tkazib yuborildi: {duration}s (limit {max_seconds}s)")
        return

    try:
        with tempfile.TemporaryDirectory(prefix="voice-transcribe-") as tmp:
            media_path = await message.download_media(file=os.path.join(tmp, "voice.ogg"))
            if not media_path:
                return
            transcript = await asyncio.to_thread(transcribe, media_path)
    except Exception as exc:
        print(f"Transkripsiya xatosi: {type(exc).__name__}: {exc}")
        return

    if not transcript:
        return
    if output_mode == "chat":
        me = await client.get_me()
        await message.reply(f"ai msg — transcribed for {me.first_name}\n\n{transcript}")
    else:
        who = get_display_name(sender)
        await client.send_message("me", f"{who} · {duration}s\n\n{transcript}")
    print(f"Transcribed {get_display_name(sender)} ({duration}s)")


async def main():
    await client.start()
    print("Ovoz transkripsiyasi ishlayapti. To'xtatish: Ctrl+C")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("To'xtatildi.")
