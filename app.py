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
beef_count = 0
pending_beef_messages = {}  # Track users who said "beef" waiting for TTS confirmation
websocket_client = None
connection_status = "Disconnected"

def check_beef_tts(message_content, username):
    """Check for beef detection and TTS confirmation logic"""
    global beef_count, pending_beef_messages
    
    # Step 1: Check if message contains "beef"
    if 'beef' in message_content.lower():
        # Store this user as having said "beef" recently
        pending_beef_messages[username] = {
            'message': message_content,
            'timestamp': datetime.now(),
            'beef_detected': True
        }
        print(f"🥩 BEEF DETECTED in message from {username}: {message_content}")
        print(f"   Waiting for TTS confirmation...")
        return False
    
    # Step 2: Check for TTS confirmation message
    # Format: "@username Your message has been queued for TTS."
    if message_content.startswith('@') and 'Your message has been queued for TTS.' in message_content:
        # Extract the username from the confirmation
        confirmed_username = message_content.split(' ')[0][1:]  # Remove @ symbol
        
        # Check if this user recently said "beef"
        if confirmed_username in pending_beef_messages:
            beef_count += 1
            beef_message = pending_beef_messages[confirmed_username]['message']
            
            print(f"🚨 BEEF TTS CONFIRMED!")
            print(f"   User: {confirmed_username}")
            print(f"   Message: {beef_message}")
            print(f"   Beef count now: {beef_count}")
            
            # Remove from pending
            del pending_beef_messages[confirmed_username]
            
            # Check if we hit the threshold
            if beef_count >= 10:
                print(f"🔥 BEEF THRESHOLD REACHED! Double TTS price!")
            
            return True
    
    return False

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
            
            # Check for beef TTS logic
            check_beef_tts(message_content, username)
        
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
                <strong>Beef TTS Count:</strong> {beef_count}/10 {"🔥 TRIGGERED!" if beef_count >= 10 else ""}<br>
                <strong>Pending Beef:</strong> {len(pending_beef_messages)} users<br>
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
            
            <div class="count" style="color: {'#FF0000' if beef_count >= 10 else '#FF4500'}; {'animation: pulse 1s infinite;' if beef_count >= 10 else ''}">{beef_count}</div>
            <div style="text-align: center; margin-bottom: 20px;">
                <strong>🥩 Beef TTS Messages (Threshold: 10)</strong>
                {f'<div style="color: #FF0000; font-weight: bold; margin-top: 10px;">🔥 TTS PRICE DOUBLED! 🔥</div>' if beef_count >= 10 else ''}
            </div>
            
            <div class="log">
                <h3>💬 Chat Messages ({len(all_chat_messages)}/30):</h3>
                {''.join([f'<div class="message"><strong>{entry.get("timestamp", "")}</strong> - <span style="color: #00aa00;">{entry.get("username", "")}</span>: {entry.get("message", "")}</div>' for entry in all_chat_messages]) if all_chat_messages else '<p>❌ No messages received yet</p>'}
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="fetch('/clear-messages', {{method: 'POST'}}).then(() => location.reload())" 
                        style="background: #6c757d; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; margin: 5px;">
                    🗑️ Clear Messages
                </button>
                <button onclick="fetch('/reset-beef', {{method: 'POST'}}).then(() => location.reload())" 
                        style="background: #dc3545; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; margin: 5px;">
                    🔄 Reset Beef Counter
                </button>
            </div>
            
            <div class="status" style="margin-top: 20px; font-size: 12px;">
                <strong>🥩 Beef TTS Counter Instructions:</strong><br>
                1. Click "🔌 Connect to Chat" to start monitoring<br>
                2. System detects messages containing "beef"<br>
                3. Waits for TTS confirmation: "@username Your message has been queued for TTS."<br>
                4. When confirmed, increments beef counter<br>
                5. At 10 beef messages → TTS price doubles + red flashing overlay<br>
                6. Add this URL to OBS as browser source: <strong>{request.host_url}overlay</strong>
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

@app.route('/api/beef-status')
def beef_status():
    """API endpoint for OBS overlay to get beef counter status"""
    global beef_count, pending_beef_messages
    return jsonify({
        'beef_count': beef_count,
        'is_triggered': beef_count >= 10,
        'pending_beef': len(pending_beef_messages),
        'threshold': 10,
        'price_doubled': beef_count >= 10,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/clear-messages', methods=['POST'])
def clear_messages():
    """Clear all chat messages"""
    global all_chat_messages
    all_chat_messages = []
    print("🗑️ Chat messages cleared")
    return jsonify({'status': 'cleared', 'message_count': len(all_chat_messages)})

@app.route('/reset-beef', methods=['POST'])
def reset_beef():
    """Reset beef counter"""
    global beef_count, pending_beef_messages
    beef_count = 0
    pending_beef_messages = {}
    print("🔄 Beef counter reset")
    return jsonify({'status': 'reset', 'beef_count': beef_count})

@app.route('/overlay')
def overlay():
    """Serve the beef counter overlay HTML for OBS"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, height=1080">
    <title>Beef Counter OBS Overlay</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            width: 1920px;
            height: 1080px;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            overflow: hidden;
        }}

        #beef-counter {{
            position: absolute;
            top: 35px;
            right: 35px;
            background: rgba(139, 69, 19, 0.9);
            color: #FFE4B5;
            padding: 15px 22px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            text-align: center;
            border: 2px solid #D2691E;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease-in-out;
            min-width: 150px;
        }}

        #beef-counter.triggered {{
            background: rgba(255, 0, 0, 0.9);
            border-color: #FF0000;
            animation: flash 1s infinite;
            transform: scale(1.1);
        }}

        @keyframes flash {{
            0%, 100% {{ 
                background: rgba(255, 0, 0, 0.9);
                box-shadow: 0 0 30px rgba(255, 0, 0, 0.8);
            }}
            50% {{ 
                background: rgba(139, 69, 19, 0.9);
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            }}
        }}

        .beef-emoji {{
            font-size: 36px;
            display: block;
            margin-bottom: 8px;
            animation: bounce 2s infinite;
        }}

        @keyframes bounce {{
            0%, 20%, 50%, 80%, 100% {{
                transform: translateY(0);
            }}
            40% {{
                transform: translateY(-10px);
            }}
            60% {{
                transform: translateY(-5px);
            }}
        }}

        .beef-title {{
            font-size: 14px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
            text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.8);
        }}

        .beef-count {{
            font-size: 36px;
            font-weight: 900;
            text-shadow: 2px 2px 3px rgba(0, 0, 0, 0.8);
            color: #FF4500;
            margin: 8px 0;
        }}

        .beef-count.triggered {{
            color: #FFFFFF;
            animation: pulse 0.5s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.2); }}
            100% {{ transform: scale(1); }}
        }}

        .beef-threshold {{
            font-size: 10px;
            opacity: 0.8;
            margin-top: 4px;
        }}

        .price-doubled {{
            font-size: 13px;
            color: #FFFFFF;
            font-weight: bold;
            background: rgba(255, 0, 0, 0.8);
            padding: 6px 9px;
            border-radius: 4px;
            margin-top: 8px;
            animation: urgentFlash 0.8s infinite;
        }}

        @keyframes urgentFlash {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}

        .last-updated {{
            position: absolute;
            bottom: 3px;
            right: 3px;
            font-size: 8px;
            opacity: 0.6;
        }}

        .error {{
            color: #FF6B6B;
            font-size: 11px;
            margin-top: 7px;
        }}
    </style>
</head>
<body>
    <div id="beef-counter">
        <span class="beef-emoji">🥩</span>
        <div class="beef-title">Beef TTS Counter</div>
        <div class="beef-count" id="count-display">0</div>
        <div class="beef-threshold">Threshold: 10 messages</div>
        <div class="price-doubled" id="price-doubled" style="display: none;">
            🔥 TTS PRICE DOUBLED! 🔥
        </div>
        <div class="last-updated" id="last-updated">—</div>
        <div class="error" id="error-message" style="display: none;"></div>
    </div>

    <script>
        const CONFIG = {{
            // Your actual Railway URL
            apiUrl: "https://web-production-e9ae0.up.railway.app/api/beef-status",
            pollMs: 2000    // Check every 2 seconds
        }};

        class BeefCounterOverlay {{
            constructor() {{
                this.currentCount = 0;
                this.isTriggered = false;
                
                this.elements = {{
                    container: document.getElementById('beef-counter'),
                    countDisplay: document.getElementById('count-display'),
                    lastUpdated: document.getElementById('last-updated'),
                    errorMessage: document.getElementById('error-message'),
                    priceDoubled: document.getElementById('price-doubled')
                }};
                
                this.init();
            }}
            
            init() {{
                this.fetchBeefCount();
                setInterval(() => this.fetchBeefCount(), CONFIG.pollMs);
            }}

            fetchBeefCount() {{
                fetch(CONFIG.apiUrl)
                    .then(response => response.json())
                    .then(data => {{
                        this.updateCounter(data.beef_count);
                        this.updateLastUpdated();
                        this.hideError();
                    }})
                    .catch(error => {{
                        console.error('Failed to fetch beef count:', error);
                        this.showError('Connection failed');
                    }});
            }}

            updateCounter(newCount) {{
                const wasTriggered = this.isTriggered;
                this.isTriggered = newCount >= 10;
                
                // Update count if changed
                if (newCount !== this.currentCount) {{
                    this.animateCountChange(newCount);
                    this.currentCount = newCount;
                }}
                
                // Handle threshold trigger
                if (this.isTriggered && !wasTriggered) {{
                    this.triggerThreshold();
                }} else if (!this.isTriggered && wasTriggered) {{
                    this.clearThreshold();
                }}
                
                // Update visual state
                this.updateVisualState();
            }}

            animateCountChange(newCount) {{
                this.elements.countDisplay.textContent = newCount;
                this.elements.countDisplay.style.animation = 'none';
                setTimeout(() => {{
                    this.elements.countDisplay.style.animation = 'pulse 0.5s ease';
                }}, 10);
            }}

            triggerThreshold() {{
                console.log('🔥 Beef threshold triggered!');
                this.elements.container.classList.add('triggered');
                this.elements.countDisplay.classList.add('triggered');
                this.elements.priceDoubled.style.display = 'block';
            }}

            clearThreshold() {{
                console.log('✅ Beef threshold cleared');
                this.elements.container.classList.remove('triggered');
                this.elements.countDisplay.classList.remove('triggered');
                this.elements.priceDoubled.style.display = 'none';
            }}

            updateVisualState() {{
                if (this.isTriggered) {{
                    this.elements.container.classList.add('triggered');
                    this.elements.countDisplay.classList.add('triggered');
                    this.elements.priceDoubled.style.display = 'block';
                }} else {{
                    this.elements.container.classList.remove('triggered');
                    this.elements.countDisplay.classList.remove('triggered');
                    this.elements.priceDoubled.style.display = 'none';
                }}
            }}

            updateLastUpdated() {{
                const now = new Date();
                this.elements.lastUpdated.textContent = `Updated: ${{now.toLocaleTimeString()}}`;
            }}

            showError(message) {{
                this.elements.errorMessage.textContent = message;
                this.elements.errorMessage.style.display = 'block';
            }}

            hideError() {{
                this.elements.errorMessage.style.display = 'none';
            }}
        }}

        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', () => {{
            new BeefCounterOverlay();
        }});
    </script>
</body>
</html>'''

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
    
    # Auto-start Pusher connection
    print("🔌 Auto-starting Pusher WebSocket connection...")
    success = start_pusher_connection()
    if success:
        print("✅ Pusher auto-start successful")
    else:
        print("❌ Pusher auto-start failed")
    
    # Get port from environment (for deployment platforms)
    port = int(os.environ.get('PORT', 5000))
    
    # Run server
    app.run(host='0.0.0.0', port=port, debug=True)