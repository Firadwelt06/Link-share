from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import hmac
import json
import os
from pathlib import Path
import socket
import threading
import uuid

APP_DIR = Path(__file__).resolve().parent
HISTORY_FILE = APP_DIR / 'links.json'
MAX_LINKS = 50

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

    return history[:MAX_LINKS]


def save_link_history(history):
    temporary_file = HISTORY_FILE.with_suffix('.json.tmp')
    with temporary_file.open('w', encoding='utf-8') as history_file:
        json.dump(history, history_file, ensure_ascii=False, indent=2)
        history_file.write('\n')
    os.replace(temporary_file, HISTORY_FILE)

app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = 'lan_link_sharer_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Keep the on-disk history and in-memory history in sync.
link_history = load_link_history()
history_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # Send existing link history to newly connected clients
    with history_lock:
        emit('load_history', link_history.copy())

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
        
        link_data = {'id': uuid.uuid4().hex, 'url': url, 'title': title}
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
    
    socketio.run(app, host='0.0.0.0', port=port, debug=True)