from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import hmac
import json
import os
from pathlib import Path
import socket
import threading
from datetime import datetime, timedelta, timezone
import uuid

APP_DIR = Path(__file__).resolve().parent
HISTORY_FILE = APP_DIR / 'links.json'
MESSAGE_FILE = APP_DIR / 'messages.json'
MAX_LINKS = 50
MAX_MESSAGES = 50
MAX_MESSAGE_LENGTH = 2000

load_dotenv(APP_DIR / '.env')


def load_link_history():
    if not HISTORY_FILE.exists():
        return []

    with HISTORY_FILE.open(encoding='utf-8') as history_file:
        history = json.load(history_file)

    if not isinstance(history, list) or any(
        not isinstance(link, dict)
        or not all(isinstance(link.get(field), str) for field in ('id', 'url', 'title'))
        for link in history
    ):
        raise ValueError(f'Invalid link history format in {HISTORY_FILE}')

    now = datetime.now(timezone.utc)
    for index, link in enumerate(history):
        if not isinstance(link.get('created_at'), str) or not link['created_at']:
            link['created_at'] = (now - timedelta(seconds=index)).isoformat()

    return history[:MAX_LINKS]


def save_link_history(history):
    temporary_file = HISTORY_FILE.with_suffix('.json.tmp')
    with temporary_file.open('w', encoding='utf-8') as history_file:
        json.dump(history, history_file, ensure_ascii=False, indent=2)
        history_file.write('\n')
    os.replace(temporary_file, HISTORY_FILE)


def load_message_history():
    if not MESSAGE_FILE.exists():
        return []

    with MESSAGE_FILE.open(encoding='utf-8') as message_file:
        messages = json.load(message_file)

    if not isinstance(messages, list) or any(
        not isinstance(message, dict)
        or not all(isinstance(message.get(field), str) for field in ('id', 'text', 'created_at'))
        for message in messages
    ):
        raise ValueError(f'Invalid message history format in {MESSAGE_FILE}')

    return messages[:MAX_MESSAGES]


def save_message_history(messages):
    temporary_file = MESSAGE_FILE.with_suffix('.json.tmp')
    with temporary_file.open('w', encoding='utf-8') as message_file:
        json.dump(messages, message_file, ensure_ascii=False, indent=2)
        message_file.write('\n')
    os.replace(temporary_file, MESSAGE_FILE)


app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = 'lan_link_sharer_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Keep the on-disk history and in-memory history in sync.
link_history = load_link_history()
message_history = load_message_history()
history_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # Send existing link history to newly connected clients
    with history_lock:
        emit('load_history', link_history.copy())
        emit('load_messages', message_history.copy())

@socketio.on('share_link')
def handle_share_link(data):
    url = data.get('url', '').strip()
    title = data.get('title', '').strip()
    
    if url:
        # Prepend http:// if missing for easy clicking
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Fallback to URL if no display name is provided
        if not title:
            title = url
        
        link_data = {
            'id': uuid.uuid4().hex,
            'url': url,
            'title': title,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        with history_lock:
            updated_history = [link_data, *link_history][:MAX_LINKS]
            try:
                save_link_history(updated_history)
            except OSError:
                app.logger.exception('Unable to save link history to %s', HISTORY_FILE)
                return {'success': False, 'message': 'Unable to save the link. Check server storage.'}
            link_history[:] = updated_history
        
        # Broadcast the new link to ALL connected devices
        emit('receive_link', link_data, broadcast=True)
        return {'success': True, 'link': link_data}


@socketio.on('share_message')
def handle_share_message(data):
    if not isinstance(data, dict):
        return {'success': False, 'message': 'Invalid message.'}
    text = data.get('text')
    if not isinstance(text, str) or not text.strip():
        return {'success': False, 'message': 'Enter a message to share.'}
    text = text.strip()
    if len(text) > MAX_MESSAGE_LENGTH:
        return {'success': False, 'message': f'Messages must be {MAX_MESSAGE_LENGTH} characters or fewer.'}

    message_data = {
        'id': uuid.uuid4().hex,
        'text': text,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    with history_lock:
        updated_history = [message_data, *message_history][:MAX_MESSAGES]
        try:
            save_message_history(updated_history)
        except OSError:
            app.logger.exception('Unable to save message history to %s', MESSAGE_FILE)
            return {'success': False, 'message': 'Unable to save the message. Check server storage.'}
        message_history[:] = updated_history

    emit('receive_message', message_data, broadcast=True)
    return {'success': True, 'message': message_data}


@socketio.on('clear_messages')
def handle_clear_messages():
    with history_lock:
        try:
            save_message_history([])
        except OSError:
            app.logger.exception('Unable to clear message history in %s', MESSAGE_FILE)
            return {'success': False, 'message': 'Unable to clear messages. Check server storage.'}
        message_history.clear()
    emit('messages_cleared', broadcast=True)
    return {'success': True}


@socketio.on('clear_links')
def handle_clear_links(data):
    configured_key = os.environ.get('LINK_CLEAR_KEY')
    provided_key = data.get('key') if isinstance(data, dict) else None

    if not configured_key:
        return {'success': False, 'message': 'Link clearing is not configured on the server.'}
    if not isinstance(provided_key, str) or not hmac.compare_digest(provided_key, configured_key):
        return {'success': False, 'message': 'Incorrect key.'}

    with history_lock:
        try:
            save_link_history([])
        except OSError:
            app.logger.exception('Unable to clear link history in %s', HISTORY_FILE)
            return {'success': False, 'message': 'Unable to clear links. Check server storage.'}
        link_history.clear()
    emit('links_cleared', broadcast=True)
    return {'success': True}

def get_local_ip():
    """Retrieve the host computer's local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    local_ip = get_local_ip()
    port = 4000
    print("\n" + "="*50)
    print(f" LAN Link Sharer is running!")
    print(f" Access it from any computer on the network at:")
    print(f" http://{local_ip}:{port}")
    print("="*50 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False)