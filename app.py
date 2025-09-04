#!/usr/bin/env python3
"""
Kick Chat Webhook Server - Production Version
Deployable to Railway, Render, Heroku, etc.
"""

import json
import hmac
import hashlib
import os
from datetime import datetime
from flask import Flask, request, jsonify
import secrets
import requests
import base64

app = Flask(__name__)

# Configuration from environment variables (for security)
CLIENT_ID = os.environ.get('KICK_CLIENT_ID', '01K49YM1DQK8CMAF1MNRQ6Z781')
CLIENT_SECRET = os.environ.get('KICK_CLIENT_SECRET', '7b67c1efe2608c5050dbbe8ab8267444bbf6ac871ab4ebafe7cdbd78a6b4188f')
WEBHOOK_SECRET = os.environ.get('KICK_WEBHOOK_SECRET', '285010f69a3dedf7337e584f01a9045e496fe122d9c19e74710c8c0870253882')
CHANNEL_NAME = "sam"

# API endpoints
KICK_API_BASE = "https://api.kick.com"
OAUTH_TOKEN_URL = "https://api.kick.com/oauth/token"

# Chat monitoring state (in-memory for simplicity)
beef_count = 0
all_chat_messages = []
access_token = None
subscription_status = "Not subscribed"

def get_oauth_token():
    """Get OAuth token for API calls"""
    global access_token
    
    try:
        print("🔐 Getting OAuth token...")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        
        response = requests.post(OAUTH_TOKEN_URL, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            print(f"✅ OAuth token obtained!")
            return access_token
        else:
            print(f"❌ OAuth error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ OAuth exception: {e}")
        return None

def subscribe_to_chat_events(webhook_url):
    """Subscribe to chat.message.sent events"""
    global subscription_status
    
    if not access_token:
        print("❌ No access token - getting one first...")
        if not get_oauth_token():
            return False
    
    try:
        print("📡 Subscribing to chat events...")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Subscribe to chat.message.sent events
        subscription_data = {
            'events': [
                {
                    'name': 'chat.message.sent',
                    'webhook_url': webhook_url
                }
            ]
        }
        
        response = requests.post(
            f"{KICK_API_BASE}/v1/events/subscribe",
            headers=headers,
            json=subscription_data,
            timeout=10
        )
        
        print(f"📡 Subscription response: {response.status_code}")
        print(f"📡 Response body: {response.text}")
        
        if response.status_code in [200, 201]:
            subscription_status = "✅ Subscribed to chat events"
            print("✅ Successfully subscribed to chat.message.sent events!")
            return True
        else:
            subscription_status = f"❌ Subscription failed: {response.status_code}"
            print(f"❌ Subscription error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        subscription_status = f"❌ Exception: {str(e)}"
        print(f"❌ Subscription exception: {e}")
        return False

def verify_webhook_signature(payload_body, signature_header):
    """Verify webhook signature from Kick"""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret set
    
    try:
        if not signature_header.startswith('sha256='):
            return False
        
        expected_signature = signature_header[7:]
        calculated_signature = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            payload_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(calculated_signature, expected_signature)
    except Exception as e:
        print(f"❌ Signature verification error: {e}")
        return False

def check_beef_message(message_content, username):
    """Check if message contains $beef and update counter"""
    global beef_count
    
    message_lower = message_content.lower().strip()
    
    if message_lower.startswith('$') and 'beef' in message_lower:
        beef_count += 1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"🥩 BEEF DETECTED! #{beef_count}")
        print(f"   User: {username}")
        print(f"   Message: {message_content}")
        print(f"   Time: {timestamp}")
        
        return True
    
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
                <strong>Channel:</strong> {CHANNEL_NAME}<br>
                <strong>Webhook URL:</strong> {request.url_root}webhook<br>
                <strong>Total Messages:</strong> {len(all_chat_messages)}<br>
                <strong>OAuth Token:</strong> {"✅ Active" if access_token else "❌ Missing"}<br>
                <strong>Event Subscription:</strong> {subscription_status}<br>
                <strong>Status:</strong> {"🟢 Online" if request.url_root else "🔴 Offline"}
            </div>
            
            <div class="status">
                <h3>🔧 Setup Actions</h3>
                <button onclick="getToken()" style="background: #007bff; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; margin: 5px;">
                    🔐 Get OAuth Token
                </button>
                <button onclick="subscribeEvents()" style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; margin: 5px;">
                    📡 Subscribe to Chat Events
                </button>
                <div id="setup-status" style="margin-top: 10px; padding: 10px; border-radius: 3px; background: #333; display: none;"></div>
            </div>
            
            <div class="count">{beef_count}</div>
            <div style="text-align: center; margin-bottom: 20px;">
                <strong>Total $beef Messages Detected</strong>
            </div>
            
            <div class="log">
                <h3>📨 Recent Messages ({len(all_chat_messages)} total):</h3>
                {''.join([f'<div class="message {'beef' if '$' in entry.get("message", "") and 'beef' in entry.get("message", "").lower() else ''}"><strong>{entry.get("timestamp", "")}</strong> - <span style="color: #00aa00;">{entry.get("username", "")}</span> [{entry.get("channel", "")}]: {entry.get("message", "")[:200]} <em>({entry.get("event_type", "")})</em></div>' for entry in all_chat_messages[-20:]]) if all_chat_messages else '<p>❌ No webhooks received yet</p>'}
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="fetch('/reset', {{method: 'POST'}}).then(() => location.reload())" 
                        style="background: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    🔄 Reset Count
                </button>
            </div>
            
            <div class="status" style="margin-top: 20px; font-size: 12px;">
                <strong>Instructions:</strong><br>
                1. Click "🔐 Get OAuth Token" first<br>
                2. Click "📡 Subscribe to Chat Events"<br>
                3. Go to kick.com/sam and type messages<br>
                4. Messages should appear here automatically!
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
            
            function getToken() {{
                showStatus('Getting OAuth token...', true);
                fetch('/get-token', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showStatus('✅ OAuth token obtained!', true);
                            setTimeout(() => location.reload(), 2000);
                        }} else {{
                            showStatus('❌ Failed to get OAuth token', false);
                        }}
                    }})
                    .catch(err => showStatus('❌ Error: ' + err.message, false));
            }}
            
            function subscribeEvents() {{
                showStatus('Subscribing to chat events...', true);
                fetch('/subscribe-events', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showStatus('✅ Subscribed to chat events!', true);
                            setTimeout(() => location.reload(), 2000);
                        }} else {{
                            showStatus('❌ Subscription failed: ' + data.error, false);
                        }}
                    }})
                    .catch(err => showStatus('❌ Error: ' + err.message, false));
            }}
        </script>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Handle incoming webhooks from Kick"""
    global all_chat_messages
    
    try:
        print(f"🔗 Webhook received from {request.remote_addr}")
        
        # Get raw payload
        raw_payload = request.get_data(as_text=True)
        print(f"📦 Payload: {raw_payload[:300]}...")
        
        # Parse JSON payload
        payload = request.get_json()
        
        if not payload:
            print("❌ No JSON payload")
            return jsonify({'error': 'No payload'}), 400
        
        print(f"📋 Payload structure: {json.dumps(payload, indent=2)[:500]}...")
        
        # Extract message information (try multiple structures)
        message_content = None
        username = None
        channel = None
        event_type = 'unknown'
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Try different payload formats
        if 'event' in payload and 'data' in payload['event']:
            data = payload['event']['data']
            event_type = payload.get('event', {}).get('type', 'unknown')
            message_content = data.get('content', data.get('message', ''))
            username = data.get('sender', {}).get('username', data.get('username', 'Unknown'))
            channel = data.get('chatroom', {}).get('channel', {}).get('slug', data.get('channel', 'unknown'))
        elif 'data' in payload:
            data = payload['data']
            event_type = payload.get('type', 'unknown')
            message_content = data.get('content', data.get('message', ''))
            username = data.get('username', data.get('user', {}).get('username', 'Unknown'))
            channel = data.get('channel', 'unknown')
        elif 'message' in payload:
            message_content = payload['message']
            username = payload.get('username', payload.get('user', 'Unknown'))
            channel = payload.get('channel', 'unknown')
            event_type = payload.get('type', payload.get('event_type', 'message'))
        else:
            # Store any webhook for debugging
            message_content = json.dumps(payload)[:200]
            username = 'WEBHOOK_DEBUG'
            channel = 'system'
            event_type = 'debug'
        
        # Store message
        if message_content:
            chat_entry = {
                'timestamp': timestamp,
                'username': username,
                'message': message_content,
                'channel': channel,
                'event_type': event_type
            }
            
            all_chat_messages.append(chat_entry)
            
            # Keep only last 100 messages
            if len(all_chat_messages) > 100:
                all_chat_messages.pop(0)
            
            print(f"💬 Message captured:")
            print(f"   Channel: {channel}")
            print(f"   User: {username}")
            print(f"   Content: {message_content}")
            print(f"   Event: {event_type}")
            
            # Check for beef
            if check_beef_message(message_content, username):
                print(f"🥩 Beef count now: {beef_count}")
        
        return jsonify({'status': 'success', 'received': True}), 200
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-token', methods=['POST'])
def get_token_route():
    """API endpoint to get OAuth token"""
    token = get_oauth_token()
    return jsonify({
        'success': token is not None,
        'message': 'OAuth token obtained' if token else 'Failed to get token'
    })

@app.route('/subscribe-events', methods=['POST'])
def subscribe_events_route():
    """API endpoint to subscribe to chat events"""
    webhook_url = request.url_root + 'webhook'
    success = subscribe_to_chat_events(webhook_url)
    return jsonify({
        'success': success,
        'error': subscription_status if not success else None,
        'webhook_url': webhook_url
    })

@app.route('/reset', methods=['POST'])
def reset_count():
    """Reset beef counter"""
    global beef_count, all_chat_messages
    beef_count = 0
    all_chat_messages = []
    print("🔄 Counter reset")
    return jsonify({'status': 'reset', 'beef_count': beef_count})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'messages_received': len(all_chat_messages),
        'beef_count': beef_count,
        'channel': CHANNEL_NAME
    })

if __name__ == '__main__':
    print("🥩 Starting Kick Chat Monitor...")
    print(f"Channel: {CHANNEL_NAME}")
    print(f"Client ID: {CLIENT_ID}")
    
    # Get port from environment (for deployment platforms)
    port = int(os.environ.get('PORT', 5000))
    
    # Run server
    app.run(host='0.0.0.0', port=port, debug=True)