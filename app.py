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

app = Flask(__name__)

# Configuration from environment variables (for security)
CLIENT_ID = os.environ.get('KICK_CLIENT_ID', '01K49YM1DQK8CMAF1MNRQ6Z781')
CLIENT_SECRET = os.environ.get('KICK_CLIENT_SECRET', '7b67c1efe2608c5050dbbe8ab8267444bbf6ac871ab4ebafe7cdbd78a6b4188f')
WEBHOOK_SECRET = os.environ.get('KICK_WEBHOOK_SECRET', '285010f69a3dedf7337e584f01a9045e496fe122d9c19e74710c8c0870253882')
CHANNEL_NAME = "sam"

# Chat monitoring state (in-memory for simplicity)
beef_count = 0
all_chat_messages = []
access_token = None

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
                <strong>Status:</strong> {"🟢 Online" if request.url_root else "🔴 Offline"}
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
                <strong>Setup Instructions:</strong><br>
                1. Go to your Kick Developer settings<br>
                2. Set webhook URL to: <code>{request.url_root}webhook</code><br>
                3. Enable webhook events<br>
                4. Save configuration
            </div>
        </div>
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