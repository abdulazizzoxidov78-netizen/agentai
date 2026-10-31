# Telegram ovozlarini matnga aylantirish

`python/voice_transcriber.py` shaxsiy chatdagi keluvchi ovozli xabar va dumaloq videolarni Groq Whisper orqali matnga aylantiradi. Asosiy Telegram agent botiga tegmaydi va alohida Telethon sessiyasidan foydalanadi.

## Bir marta o'rnatish

PowerShell yoki CMD'da loyiha papkasiga o'ting:

```bat
cd /d "%USERPROFILE%\Desktop\agent"
python -m pip install -r python\requirements.txt
```

`.env` ichida quyidagi qiymatlar borligini tekshiring (kalitlarni hech kimga yubormang):

```env
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
GROQ_API_KEY=gsk_...
VOICE_OUTPUT=chat
VOICE_MAX_SECONDS=600
```

`VOICE_OUTPUT=chat` transkripsiyani shu suhbatga javob qilib yuboradi. `VOICE_OUTPUT=me` faqat Saved Messages'ga yozadi.

## Ishga tushirish

```bat
python python\voice_transcriber.py
```

Birinchi ishga tushganda Telegram telefon raqami, ilovaga kelgan login kodi va akkauntda yoqilgan bo'lsa 2 bosqichli parol so'raladi. Shu terminal oynasi ochiq turganda ishlaydi. Keyin ishga tushirish uchun `start_voice_transcriber.bat` faylini ochish kifoya.

Sessiya `python\voice_transcriber_session.session` faylida saqlanadi. Uni hech kimga bermang yoki GitHub'ga yuklamang. Agar kompyuteringizda boshqa dastur ayni akkaunt sessiyasidan ayni vaqtda foydalansa, ularga alohida sessiyalar kerak.
