import os
import asyncio
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from telethon import TelegramClient

BASE = Path(__file__).resolve().parent.parent
for line in (BASE / '.env').read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"\''))

api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
if not api_id or not api_hash:
    raise RuntimeError('TELEGRAM_API_ID va TELEGRAM_API_HASH .env faylida kerak.')

mcp = FastMCP('telegram')


def make_client():
    return TelegramClient(
        str(BASE / 'python' / 'telegram_codex_session'), int(api_id), api_hash
    )


def resolve_peer(chat: str):
    value = chat.strip()
    return int(value) if value.lstrip('-').isdigit() else value


def display_name(entity) -> str:
    title = getattr(entity, 'first_name', None) or getattr(entity, 'title', None) or ''
    username = getattr(entity, 'username', None)
    return f'{title} (@{username})' if username else title


@mcp.tool()
async def list_dialogs(limit: int = 30) -> str:
    """Telegram chatlarining nomi, turi va ID raqamini chiqaradi."""
    async with make_client() as client:
        rows = []
        async for dialog in client.iter_dialogs(limit=max(1, min(limit, 100))):
            kind = 'group' if dialog.is_group else 'channel' if dialog.is_channel else 'user'
            rows.append(f'{dialog.name} | {kind} | id={dialog.id}')
        return '\n'.join(rows) or '(chat yo‘q)'


@mcp.tool()
async def read_messages(chat: str, limit: int = 30) -> str:
    """Ko‘rsatilgan chatning oxirgi xabarlarini o‘qiydi. Chat username yoki ID bo‘lishi mumkin."""
    async with make_client() as client:
        rows = []
        async for message in client.iter_messages(
            resolve_peer(chat), limit=max(1, min(limit, 100))
        ):
            if message.text:
                sender = await message.get_sender()
                author = display_name(sender) if sender else str(message.sender_id)
                rows.append(f'[{message.date:%Y-%m-%d %H:%M}] {author}: {message.text}')
        return '\n'.join(reversed(rows)) or '(matnli xabar topilmadi)'


@mcp.tool()
async def search_messages(chat: str, query: str, limit: int = 30) -> str:
    """Berilgan chat ichida matn bo‘yicha xabar qidiradi."""
    async with make_client() as client:
        rows = []
        async for message in client.iter_messages(
            resolve_peer(chat), search=query, limit=max(1, min(limit, 100))
        ):
            if message.text:
                rows.append(f'[{message.date:%Y-%m-%d %H:%M}] {message.text}')
        return '\n'.join(reversed(rows)) or '(topilmadi)'


@mcp.tool()
async def send_message(recipient: str, text: str, confirm: bool = False) -> str:
    """Avval preview ko‘rsatadi; xabar faqat confirm=true bo‘lganda yuboriladi."""
    async with make_client() as client:
        entity = await client.get_entity(resolve_peer(recipient))
        if not confirm:
            return (
                f'PREVIEW — yuborilmadi.\nKimga: {display_name(entity) or recipient}'
                f'\nMatn: {text}\nTasdiqlash uchun confirm=true bilan qayta chaqiring.'
            )
        await client.send_message(entity, text)
        return f'Yuborildi: {display_name(entity) or recipient}'


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--login':
        async def login():
            async with make_client() as client:
                account = await client.get_me()
                print(f'Codex MCP login muvaffaqiyatli: {account.first_name}')

        asyncio.run(login())
    else:
        mcp.run()
