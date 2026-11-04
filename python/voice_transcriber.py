"""Transcribe incoming Telegram voice notes and round videos."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
import librosa
import imageio_ffmpeg
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
    # 0 means no duration limit; a positive value sets an optional limit.
    max_seconds = int(os.getenv("VOICE_MAX_SECONDS", "0"))
    if max_seconds < 0:
        raise ValueError
except ValueError:
    raise SystemExit("VOICE_MAX_SECONDS 0 yoki musbat butun son bo'lishi kerak.")

# A separate session avoids colliding with the project's existing Telethon session.
client = TelegramClient(str(ROOT / "python" / "voice_transcriber_session"), int(api_id), api_hash)
model_id = os.getenv("UZBEK_STT_MODEL", "Kotib/uzbek_stt_v1")
processor = None
asr_model = None


def transcribe(path: str) -> str:
    global processor, asr_model
    if processor is None or asr_model is None:
        print(f"O'zbekcha model yuklanmoqda: {model_id} (birinchi marta ~3 GB)...", file=sys.stderr)
        processor = WhisperProcessor.from_pretrained(model_id)
        asr_model = WhisperForConditionalGeneration.from_pretrained(model_id).eval()

    # Voice notes are usually OGG/Opus; round videos are MP4. Convert either
    # container through the bundled FFmpeg before decoding the audio.
    wav_path = str(Path(path).with_name("audio.wav"))
    result = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", path, "-vn", "-ac", "1",
         "-ar", "16000", "-f", "wav", wav_path],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(f"Audio ajratilmadi: {result.stderr[-1200:]}")
    audio, sample_rate = librosa.load(wav_path, sr=16000, mono=True)
    # Whisper accepts about 30 seconds per input. Split longer round videos
    # into supported chunks instead of silently truncating or mis-decoding them.
    chunk_size = 30 * sample_rate
    transcripts = []
    for start in range(0, len(audio), chunk_size):
        chunk = audio[start:start + chunk_size]
        if len(chunk) < int(0.25 * sample_rate):
            continue
        features = processor(
            chunk, sampling_rate=sample_rate, return_tensors="pt"
        ).input_features
        with torch.inference_mode():
            token_ids = asr_model.generate(
                features,
                language="uz",
                task="transcribe",
                num_beams=5,
                do_sample=False,
            )
        text = processor.batch_decode(
            token_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()
        if text:
            transcripts.append(text)
    return " ".join(transcripts)


@client.on(events.NewMessage(incoming=True))
async def handle_voice(event):
    message = event.message
    # Handle private chats, groups, and supergroups; reply in the source chat.
    if not (message.voice or message.video_note):
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return
    duration = int(getattr(message.file, "duration", 0) or 0)
    if max_seconds and duration > max_seconds:
        print(f"O'tkazib yuborildi: {duration}s (limit {max_seconds}s)")
        return

    try:
        with tempfile.TemporaryDirectory(prefix="voice-transcribe-") as tmp:
            # Telethon chooses a filename with the media's actual format.
            media_path = await message.download_media(file=tmp)
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
        heading = f"Ovozli xabar matni ({me.first_name}):\n\n"
        destination = event.chat_id
    else:
        who = get_display_name(sender)
        heading = f"{who} - {duration} soniya\n\n"
        destination = "me"

    # Telegram limits a text message to 4096 characters. Split long transcripts
    # at word boundaries and put the heading only on the first part.
    limit = 3800
    parts = []
    remaining = transcript
    while len(remaining) > limit:
        cut = remaining.rfind(" ", 0, limit)
        if cut < 1:
            cut = limit
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    parts.append(remaining)
    for index, part in enumerate(parts):
        text = (heading if index == 0 else f"Davomi ({index + 1}/{len(parts)}):\n\n") + part
        if output_mode == "chat" and index == 0:
            await message.reply(text)
        else:
            await client.send_message(destination, text)
    print(f"Transcribed {get_display_name(sender)} ({duration}s)")


async def main():
    await client.start()
    print("Ovoz transkripsiyasi ishlayapti. To'xtatish: Ctrl+C")
    await client.run_until_disconnected()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--worker":
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                transcript = transcribe(request["path"])
                response = {"id": request.get("id"), "text": transcript}
            except Exception as exc:
                response = {"id": request.get("id"),
                            "error": f"{type(exc).__name__}: {exc}"}
            print(json.dumps(response, ensure_ascii=False), flush=True)
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--transcribe-file":
        try:
            print(transcribe(sys.argv[2]))
        except Exception as exc:
            print(f"Transkripsiya xatosi: {type(exc).__name__}: {exc}", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("To'xtatildi.")
