#!/usr/bin/env python3
"""
Kick Chat Monitor - Pusher WebSocket Version
Monitors Kick.com chat via Pusher WebSocket connection
"""

import json
import os
import asyncio
import threading
from datetime import datetime
from flask import Flask, request, jsonify
import websocket
import time

app = Flask(__name__)

# Pusher Configuration
PUSHER_APP_KEY = "32cbd69e4b950bf97679"
PUSHER_CLUSTER = "us2"
PUSHER_WS_URL = f"wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_APP_KEY}?protocol=7&client=js&version=8.4.0&flash=false"
CHANNEL_NAME = "sam"
CHATROOM_ID = 328681  # From your message example

# Chat monitoring state (in-memory for simplicity)
all_chat_messages = []
websocket_client = None
connection_status = "Disconnected"


def on_pusher_message(ws, message):
    """Handle incoming Pusher WebSocket messages"""
    global all_chat_messages, connection_status
    
    try:
        # Parse Pusher message
        data = json.loads(message)
        
        # Handle different Pusher event types
        if data.get('event') == 'pusher:connection_established':
            connection_data = json.loads(data.get('data', '{}'))
            connection_status = "✅ Connected to Pusher"
            print(f"🔌 Connected to Pusher! Socket ID: {connection_data.get('socket_id', 'unknown')}")
            
            # Subscribe to the chatroom channel
            subscribe_msg = {
                "event": "pusher:subscribe",
                "data": {
                    "channel": f"chatrooms.{CHATROOM_ID}.v2"
                }
            }
            ws.send(json.dumps(subscribe_msg))
            print(f"📡 Subscribing to channel: chatrooms.{CHATROOM_ID}.v2")
            
        elif data.get('event') == 'pusher:subscription_succeeded':
            print(f"✅ Subscribed to channel: {data.get('channel')}")
            connection_status = f"✅ Subscribed to chatrooms.{CHATROOM_ID}.v2"
            
        elif data.get('event') == 'App\\Events\\ChatMessageEvent':
            # This is a chat message!
            message_data = json.loads(data.get('data', '{}'))
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Extract message info using your provided format
            message_content = message_data.get('content', '')
            username = message_data.get('sender', {}).get('username', 'Unknown')
            user_id = message_data.get('sender', {}).get('id', 0)
            message_id = message_data.get('id', '')
            
            # Store the message
            chat_entry = {
                'timestamp': timestamp,
                'username': username,
                'message': message_content,
                'message_id': message_id,
                'user_id': user_id
            }
            
            all_chat_messages.append(chat_entry)
            
            # Keep only last 30 messages
            if len(all_chat_messages) > 30:
                all_chat_messages.pop(0)
            
            print(f"💬 {username}: {message_content}")
        
        else:
            # Log other events for debugging
            print(f"📨 Pusher event: {data.get('event')} on channel {data.get('channel')}")
            
    except Exception as e:
        print(f"❌ Error parsing Pusher message: {e}")
        print(f"❌ Raw message: {message}")

def on_pusher_error(ws, error):
    """Handle Pusher WebSocket errors"""
    global connection_status
    connection_status = f"❌ Error: {str(error)}"
    print(f"❌ Pusher WebSocket error: {error}")

def on_pusher_close(ws, close_status_code, close_msg):
    """Handle Pusher WebSocket close"""
    global connection_status
    connection_status = "❌ Disconnected"
    print(f"🔌 Pusher WebSocket closed: {close_status_code} - {close_msg}")

def on_pusher_open(ws):
    """Handle Pusher WebSocket open"""
    global connection_status
    connection_status = "🔌 Connected, waiting for auth"
    print("🔌 Pusher WebSocket opened!")

def start_pusher_connection():
    """Start the Pusher WebSocket connection"""
    global websocket_client, connection_status
    
    try:
        print(f"🔌 Connecting to Pusher: {PUSHER_WS_URL}")
        
        websocket.enableTrace(False)  # Set to True for debugging
        
        websocket_client = websocket.WebSocketApp(
            PUSHER_WS_URL,
            header={
                'Origin': 'https://kick.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            on_message=on_pusher_message,
            on_error=on_pusher_error,
            on_close=on_pusher_close,
            on_open=on_pusher_open
        )
        
        # Run WebSocket in a separate thread
        def run_websocket():
            websocket_client.run_forever()
        
        ws_thread = threading.Thread(target=run_websocket, daemon=True)
        ws_thread.start()
        
        connection_status = "🔌 Connecting..."
        print("🔌 Pusher WebSocket connection started in background")
        return True
        
    except Exception as e:
        connection_status = f"❌ Failed to start: {str(e)}"
        print(f"❌ Failed to start Pusher connection: {e}")
        return False


@app.route('/')
def dashboard():
    """Simple dashboard"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kick Chat Monitor - Channel: {CHANNEL_NAME}</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: white; }}
            .container {{ max-width: 900px; margin: 0 auto; }}
            .count {{ font-size: 48px; color: #FF4500; text-align: center; margin: 20px 0; }}
            .status {{ background: #333; padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .log {{ background: #222; padding: 10px; border-radius: 5px; max-height: 400px; overflow-y: auto; margin: 10px 0; }}
            .message {{ background: #4a2c17; margin: 5px 0; padding: 8px; border-radius: 3px; border-left: 3px solid #D2691E; }}
            .beef {{ background: #2c4a17; border-left: 3px solid #00aa00; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🥩 Kick Chat Monitor</h1>
            <div class="status">
                <strong>Channel:</strong> {CHANNEL_NAME} (Chatroom ID: {CHATROOM_ID})<br>
                <strong>Pusher Connection:</strong> {connection_status}<br>
                <strong>Total Messages:</strong> {len(all_chat_messages)}<br>
                <strong>WebSocket URL:</strong> ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_APP_KEY}<br>
                <strong>Status:</strong> {"🟢 Online" if request.url_root else "🔴 Offline"}
            </div>
            
            <div class="status">
                <h3>🔌 Pusher Controls</h3>
                <button onclick="connectPusher()" style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; margin: 5px;">
                    🔌 Connect to Chat
                </button>
                <button onclick="disconnectPusher()" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; margin: 5px;">
                    🔌 Disconnect
                </button>
                <div id="setup-status" style="margin-top: 10px; padding: 10px; border-radius: 3px; background: #333; display: none;"></div>
            </div>
            
            <div class="count">{len(all_chat_messages)}</div>
            <div style="text-align: center; margin-bottom: 20px;">
                <strong>Total Chat Messages (Last 30)</strong>
            </div>
            
            <div class="log">
                <h3>💬 Chat Messages ({len(all_chat_messages)}/30):</h3>
                {''.join([f'<div class="message"><strong>{entry.get("timestamp", "")}</strong> - <span style="color: #00aa00;">{entry.get("username", "")}</span>: {entry.get("message", "")}</div>' for entry in all_chat_messages]) if all_chat_messages else '<p>❌ No messages received yet</p>'}
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="fetch('/clear-messages', {{method: 'POST'}}).then(() => location.reload())" 
                        style="background: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    🗑️ Clear Messages
                </button>
            </div>
            
            <div class="status" style="margin-top: 20px; font-size: 12px;">
                <strong>🚀 Instructions:</strong><br>
                1. Click "🔌 Connect to Chat" to start monitoring<br>
                2. Go to kick.com/sam and type messages<br>
                3. All chat messages will appear here in real-time!<br>
                4. Only keeps the last 30 messages (automatically clears oldest)
            </div>
        </div>
        
        <script>
            function showStatus(message, success) {{
                const statusDiv = document.getElementById('setup-status');
                statusDiv.style.display = 'block';
                statusDiv.style.background = success ? '#2a4a17' : '#4a1717';
                statusDiv.textContent = message;
                setTimeout(() => {{ statusDiv.style.display = 'none'; }}, 5000);
            }}
            
            function connectPusher() {{
                showStatus('Connecting to Pusher WebSocket...', true);
                fetch('/connect-pusher', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showStatus('✅ Connected to Kick chat!', true);
                            setTimeout(() => location.reload(), 2000);
                        }} else {{
                            showStatus('❌ Failed to connect: ' + data.error, false);
                        }}
                    }})
                    .catch(err => showStatus('❌ Error: ' + err.message, false));
            }}
            
            function disconnectPusher() {{
                showStatus('Disconnecting from Pusher...', true);
                fetch('/disconnect-pusher', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        showStatus('✅ Disconnected', true);
                        setTimeout(() => location.reload(), 1000);
                    }})
                    .catch(err => showStatus('❌ Error: ' + err.message, false));
            }}
        </script>
    </body>
    </html>
    '''

@app.route('/connect-pusher', methods=['POST'])
def connect_pusher_route():
    """API endpoint to start Pusher WebSocket connection"""
    success = start_pusher_connection()
    return jsonify({
        'success': success,
        'status': connection_status,
        'error': connection_status if not success else None
    })

@app.route('/disconnect-pusher', methods=['POST'])
def disconnect_pusher_route():
    """API endpoint to disconnect Pusher WebSocket"""
    global websocket_client, connection_status
    
    try:
        if websocket_client:
            websocket_client.close()
            websocket_client = None
        
        connection_status = "❌ Disconnected"
        return jsonify({
            'success': True,
            'status': connection_status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/clear-messages', methods=['POST'])
def clear_messages():
    """Clear all chat messages"""
    global all_chat_messages
    all_chat_messages = []
    print("🗑️ Chat messages cleared")
    return jsonify({'status': 'cleared', 'message_count': len(all_chat_messages)})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'messages_received': len(all_chat_messages),
        'connection_status': connection_status,
        'channel': CHANNEL_NAME
    })

if __name__ == '__main__':
    print("💬 Starting Kick Chat Monitor...")
    print(f"Channel: {CHANNEL_NAME} (Chatroom ID: {CHATROOM_ID})")
    print(f"Pusher App Key: {PUSHER_APP_KEY}")
    print(f"WebSocket URL: {PUSHER_WS_URL}")
    print("📊 Tracking all chat messages (max 30)")
    
    # Get port from environment (for deployment platforms)
    port = int(os.environ.get('PORT', 5000))
    
    # Run server
    app.run(host='0.0.0.0', port=port, debug=True)