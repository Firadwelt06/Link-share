🌐 LAN Link Sharer
A real-time local network utility that allows you to seamlessly share links from one computer to all other devices connected to the same Wi-Fi or Ethernet network instantly.

How It Works
Running the host server spins up a local web instance accessible via the host's local IP address. Using WebSockets, any link submitted with an optional custom title is instantly pushed and rendered across all connected browser windows without requiring page reloads.

Tech Stack: Python, Flask, Flask-SocketIO, HTML5, JavaScript, WebSockets.

Key Features: Zero-latency real-time link broadcasting, custom alias naming, persistent in-memory session history, and automated local IP detection.