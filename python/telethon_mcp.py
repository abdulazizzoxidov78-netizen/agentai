import sys
import json
import asyncio
import os
from telethon import TelegramClient
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
        normalized_query = query.lstrip('@').casefold()
        dialogs = await client.get_dialogs()
        results = []
        for d in dialogs:
            username = getattr(d.entity, 'username', None) or ''
            if normalized_query in d.name.casefold() or normalized_query in username.casefold():
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
        await client.send_message(entity, text)
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
