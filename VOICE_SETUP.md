# Telegram ovozlarini matnga aylantirish

`python/voice_transcriber.py` shaxsiy chatlar, guruhlar va superguruhlardagi keluvchi ovozli xabar hamda dumaloq videolarni kompyuterning o'zida Kotib Uzbek Whisper modeli orqali matnga aylantiradi. Groq API kaliti talab qilinmaydi. Asosiy Telegram agent botiga tegmaydi va alohida Telethon sessiyasidan foydalanadi.

## Bir marta o'rnatish

PowerShell yoki CMD'da loyiha papkasiga o'ting:

```bat
cd /d "%USERPROFILE%\Desktop\agent"
python -m pip install -r python\requirements.txt
```

`.env` ichida quyidagi Telegram API qiymatlari bo'lishi kerak:

```env
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
VOICE_OUTPUT=chat
VOICE_MAX_SECONDS=0
```

`VOICE_OUTPUT=chat` (standart) transkripsiyani kelgan ovozli xabar yoki dumaloq video turgan chatga javob qilib yuboradi; guruh a'zolari ham javobni ko'radi. `VOICE_OUTPUT=me` faqat Saved Messages'ga yozadi. `VOICE_MAX_SECONDS=0` davomiylik limitini olib tashlaydi; transkripsiya juda uzun bo'lsa, Telegram xabar chegarasi sabab bir necha xabarga bo'lib yuboriladi. Limit qo'ymoqchi bo'lsangiz, masalan `VOICE_MAX_SECONDS=600` deb belgilang.

## Ishga tushirish

```bat
python python\voice_transcriber.py
```

Birinchi ishga tushganda Kotib modeli (~3 GB) yuklanadi; internet va disk joyi kerak. Saqlangan Telegram sessiyasi bo'lsa qayta login shart emas. Dasturni yangilashdan keyin PowerShell'da `python -m pip install -r python\requirements.txt` buyrug'ini bir marta bajaring. So'ng `start_voice_transcriber.bat` faylini oching; dastur ishlashi uchun terminal oynasi ochiq tursin. Ovozli xabar va dumaloq videolar FFmpeg orqali to'g'ri audio formatiga o'tkaziladi.

Sessiya `python\voice_transcriber_session.session` faylida saqlanadi. Uni hech kimga bermang yoki GitHub'ga yuklamang. Agar kompyuteringizda boshqa dastur ayni akkaunt sessiyasidan ayni vaqtda foydalansa, ularga alohida sessiyalar kerak.

## Kotib botiga yuborilgan media

Loyihaning Telegram botiga shaxsiy chatda yuborilgan ovozli xabar yoki dumaloq video ham matnga aylantiriladi. Buning uchun bot `npm start` buyrug'i bilan ishlayotgan bo'lishi, `.env` dagi `BOT_TOKEN` va `MY_ID` to'g'ri bo'lishi kerak. Bot chatiga yuborilgan media bot chatida matn javobi oladi; shaxsiy akkauntga kelgan media esa kelgan chatning o'zida javob oladi.
