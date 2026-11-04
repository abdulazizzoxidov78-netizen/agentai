import sys
import json
import asyncio
import os
import re
import unicodedata

if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient, events
from telethon.utils import get_display_name
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.isfile(env_path):
    with open(env_path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))

API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_NAME = os.path.join(os.path.dirname(__file__), 'telethon_session')

client = TelegramClient(SESSION_NAME, int(API_ID) if API_ID else 0, API_HASH or '')
AUTO_REPLY_ENABLED = os.getenv('TELEGRAM_AUTO_REPLY', 'true').strip().lower() != 'false'


@client.on(events.NewMessage(incoming=True))
async def forward_private_message(event):
    if not AUTO_REPLY_ENABLED or not event.is_private:
        return
    message = event.message
    text = (message.raw_text or '').strip()
    if not text:
        return
    sender = await event.get_sender()
    if getattr(sender, 'bot', False):
        return
    print(json.dumps({
        'event': 'incoming_private_message',
        'chat_id': event.chat_id,
        'message_id': message.id,
        'sender_id': getattr(sender, 'id', None),
        'sender_name': get_display_name(sender),
        'text': text,
    }, ensure_ascii=False), flush=True)


def normalize_search_words(value):
    value = unicodedata.normalize('NFKC', str(value)).casefold().replace('ё', 'е')
    words = re.findall(r'[\w]+', value, flags=re.UNICODE)
    stop_words = {'menga', 'manga', 'degan', 'digan', 'chat', 'chatni', 'chatini',
                  'chatlar', 'chatlari', 'orasidan', 'topib', 'top', 'qidirib',
                  'qidir', 'unga', 'un', 'ga', 'iltimos'}
    normalized = []
    for word in words:
        if word in stop_words:
            continue
        # Uzbek possessive endings commonly appear in casual chat requests.
        if len(word) > 3 and word.endswith('m'):
            word = word[:-1]
        elif len(word) > 4 and word.endswith('si'):
            word = word[:-2]
        if word:
            normalized.append(word)
    return normalized


def chat_matches_query(name, username, query_words):
    candidate_words = normalize_search_words(f'{name} {username or ""}')
    return bool(query_words) and all(
        any(candidate.startswith(word) or word.startswith(candidate)
            for candidate in candidate_words)
        for word in query_words
    )


async def resolve_entity(chat_id):
    """Resolve numeric dialog IDs via the session's dialogs to retain access hashes."""
    value = str(chat_id).strip()
    if value.lstrip('-').isdigit():
        numeric_id = int(value)
        async for dialog in client.iter_dialogs():
            if dialog.id == numeric_id:
                return dialog.entity
    return await client.get_entity(int(value) if value.lstrip('-').isdigit() else value)

async def handle_request(request):
    method = request.get('method')
    params = request.get('params', {})
    
    if method == 'search_chats':
        query = params.get('query', '')
        query_words = normalize_search_words(query.lstrip('@'))
        dialogs = await client.get_dialogs()
        results = []
        for d in dialogs:
            username = getattr(d.entity, 'username', None) or ''
            if chat_matches_query(d.name, username, query_words):
                results.append({'id': d.id, 'name': d.name})
        return results

    elif method == 'get_messages':
        chat_id = params.get('chat_id')
        limit = params.get('limit', 10)
        entity = await resolve_entity(chat_id)
        messages = await client.get_messages(entity, limit=limit)
        return [{'id': m.id, 'text': m.text, 'sender_id': m.sender_id} for m in messages]

    elif method == 'send_message':
        chat_id = params.get('chat_id')
        text = params.get('text')
        if not chat_id or not text:
            raise ValueError('chat_id va text kiritilishi shart')
        entity = await resolve_entity(chat_id)
        if not params.get('confirm', False):
            label = getattr(entity, 'title', None) or getattr(entity, 'first_name', None) or str(chat_id)
            return {'status': 'preview', 'recipient': label, 'text': text}
        send_options = {}
        if params.get('reply_to') is not None:
            send_options['reply_to'] = int(params['reply_to'])
        await client.send_message(entity, text, **send_options)
        return {'status': 'sent'}

    elif method == 'status':
        is_auth = await client.is_user_authorized()
        return {'authorized': is_auth}

    else:
        raise ValueError(f"Unknown method: {method}")

async def main():
    if not API_ID or not API_HASH:
        print('TELEGRAM_API_ID va TELEGRAM_API_HASH .env faylida sozlanmagan.', file=sys.stderr)
        return
    await client.connect()
    
    # If not authorized, the user will need to run this script once interactively
    if not await client.is_user_authorized():
        print(json.dumps({'event': 'error', 'error': 'Avval python python/telethon_mcp.py --login buyrug‘ini ishga tushiring.'}), flush=True)
        await client.disconnect()
        return

    while True:
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        
        try:
            request = json.loads(line)
            result = await handle_request(request)
            print(json.dumps({'id': request.get('id'), 'result': result}), flush=True)
        except Exception as e:
            print(json.dumps({'id': request.get('id'), 'error': str(e)}), flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--login':
        if not API_ID or not API_HASH:
            raise SystemExit('TELEGRAM_API_ID va TELEGRAM_API_HASH .env faylida sozlang.')
        # Interactive login
        async def login():
            await client.start()
            print("Successfully logged in!")
        asyncio.run(login())
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            # Ctrl+C is a normal way to stop the bot and its MCP child process.
            pass
