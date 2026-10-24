from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import hmac
import os
from pathlib import Path
import socket
import uuid

load_dotenv(Path(__file__).resolve().with_name('.env'))

app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = 'lan_link_sharer_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory history of shared links
link_history = []

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # Send existing link history to newly connected clients
    emit('load_history', link_history)

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
        link_history.insert(0, link_data)  # Add to top of history
        
        # Keep history manageable (e.g., last 50 links)
        if len(link_history) > 50:
            link_history.pop()
            
        # Broadcast the new link to ALL connected devices
        emit('receive_link', link_data, broadcast=True)

@socketio.on('clear_links')
def handle_clear_links(data):
    configured_key = os.environ.get('LINK_CLEAR_KEY')
    provided_key = data.get('key') if isinstance(data, dict) else None

    if not configured_key:
        return {'success': False, 'message': 'Link clearing is not configured on the server.'}
    if not isinstance(provided_key, str) or not hmac.compare_digest(provided_key, configured_key):
        return {'success': False, 'message': 'Incorrect key.'}

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