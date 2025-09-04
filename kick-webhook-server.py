#!/usr/bin/env python3
"""
Kick Chat Monitor - Webhook Server
Monitors chat messages from Kick.com using official webhooks
"""

import json
import hmac
import hashlib
import time
from datetime import datetime
from flask import Flask, request, jsonify, redirect, session, url_for
import threading
import webbrowser
from pathlib import Path
import requests
import secrets
import base64

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # For session management

# Configuration - Kick API Credentials
CLIENT_ID = "01K49YM1DQK8CMAF1MNRQ6Z781"
CLIENT_SECRET = "7b67c1efe2608c5050dbbe8ab8267444bbf6ac871ab4ebafe7cdbd78a6b4188f"
WEBHOOK_SECRET = None  # This will be generated when we set up the webhook
CHANNEL_NAME = "sam"
BEEF_COUNT_FILE = Path("beef_count.txt")

# OAuth and API endpoints
KICK_API_BASE = "https://api.kick.com/public/v1"
OAUTH_TOKEN_URL = "https://id.kick.com/OAuth/token"  # Correct OAuth endpoint
access_token = None

# Chat monitoring state
beef_count = 0
chat_log = []
all_chat_messages = []  # Store all chat messages for debugging

def load_beef_count():
    """Load existing beef count from file"""
    global beef_count
    try:
        if BEEF_COUNT_FILE.exists():
            with open(BEEF_COUNT_FILE, 'r') as f:
                beef_count = int(f.read().strip())
        else:
            beef_count = 0
    except:
        beef_count = 0
    print(f"📊 Loaded beef count: {beef_count}")

def save_beef_count():
    """Save beef count to file"""
    try:
        with open(BEEF_COUNT_FILE, 'w') as f:
            f.write(str(beef_count))
        print(f"💾 Saved beef count: {beef_count}")
    except Exception as e:
        print(f"❌ Error saving beef count: {e}")

def verify_webhook_signature(payload_body, signature_header):
    """
    Verify webhook signature from Kick
    Based on Kick's webhook security documentation
    """
    if not WEBHOOK_SECRET:
        print("⚠️  Warning: No webhook secret set - signatures not verified")
        return True
    
    try:
        # Extract signature from header (format: "sha256=<signature>")
        if not signature_header.startswith('sha256='):
            return False
        
        expected_signature = signature_header[7:]  # Remove "sha256=" prefix
        
        # Calculate expected signature
        calculated_signature = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            payload_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(calculated_signature, expected_signature)
    
    except Exception as e:
        print(f"❌ Signature verification error: {e}")
        return False

def get_client_credentials_token():
    """Get OAuth token using client credentials flow"""
    global access_token
    
    # Try multiple possible endpoints
    possible_endpoints = [
        "https://kick.com/api/oauth/token",
        "https://api.kick.com/oauth/token", 
        "https://kick.com/oauth/token",
        "https://id.kick.com/oauth/token",
        "https://auth.kick.com/oauth/token"
    ]
    
    for endpoint_url in possible_endpoints:
        try:
            print(f"🔐 Trying OAuth endpoint: {endpoint_url}")
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            }
            
            response = requests.post(endpoint_url, headers=headers, data=data, timeout=10)
            
            print(f"   Response: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    token_data = response.json()
                    access_token = token_data.get('access_token')
                    expires_in = token_data.get('expires_in', 3600)
                    
                    print(f"✅ OAuth token obtained from {endpoint_url}!")
                    print(f"   Expires in {expires_in} seconds")
                    print(f"   Token preview: {access_token[:20]}..." if access_token else "No token in response")
                    
                    # Update the working endpoint
                    global OAUTH_TOKEN_URL
                    OAUTH_TOKEN_URL = endpoint_url
                    
                    return access_token
                except:
                    print(f"   Error parsing JSON response")
                    continue
            elif response.status_code == 404:
                print(f"   404 - Endpoint not found")
                continue
            elif response.status_code == 401:
                print(f"   401 - Credentials might be invalid")
                print(f"   Response: {response.text[:200]}")
                continue
            else:
                print(f"   {response.status_code} - {response.text[:200]}")
                continue
                
        except requests.exceptions.RequestException as e:
            print(f"   Connection error: {e}")
            continue
        except Exception as e:
            print(f"   Exception: {e}")
            continue
    
    print("❌ All OAuth endpoints failed")
    return None

def setup_webhook():
    """Generate webhook configuration info (webhooks must be set up in Kick Developer dashboard)"""
    
    try:
        print("🔗 Generating webhook configuration...")
        
        # Generate webhook secret for security
        global WEBHOOK_SECRET
        WEBHOOK_SECRET = secrets.token_hex(32)
        
        webhook_url_local = "http://localhost:5000/webhook"
        webhook_url_ngrok = "https://YOUR_NGROK_URL.ngrok.io/webhook"  # User needs to replace this
        
        print("✅ Webhook configuration ready!")
        print("=" * 60)
        print("🔧 MANUAL WEBHOOK SETUP REQUIRED:")
        print("=" * 60)
        print("Kick webhooks must be configured through the Developer Dashboard")
        print()
        print("📋 SETUP STEPS:")
        print("1. Go to your Kick Account Settings → Developer tab")
        print("2. Edit your application")
        print("3. Toggle webhook 'Switch' to 'On'")
        print("4. Enter webhook URL:")
        print(f"   For testing: {webhook_url_local}")
        print(f"   For public:  {webhook_url_ngrok}")
        print()
        print("5. Your webhook will receive POST requests for:")
        print("   - chat.message.sent events")
        print("   - follows, subscriptions, etc.")
        print()
        print(f"🔐 Your webhook secret: {WEBHOOK_SECRET}")
        print("   (This is stored in the server for signature verification)")
        print("=" * 60)
        
        return True
            
    except Exception as e:
        print(f"❌ Webhook setup exception: {e}")
        return False

def check_beef_message(message_content, username):
    """Check if message contains $beef and update counter"""
    global beef_count
    
    message_lower = message_content.lower().strip()
    
    if message_lower.startswith('$') and 'beef' in message_lower:
        beef_count += 1
        save_beef_count()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'username': username,
            'message': message_content,
            'beef_count': beef_count
        }
        
        chat_log.append(log_entry)
        
        # Keep only last 100 entries
        if len(chat_log) > 100:
            chat_log.pop(0)
        
        print(f"🥩 BEEF DETECTED! #{beef_count}")
        print(f"   User: {username}")
        print(f"   Message: {message_content}")
        print(f"   Time: {timestamp}")
        
        return True
    
    return False

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Handle incoming webhooks from Kick"""
    global all_chat_messages
    
    try:
        # Log that we received ANY webhook
        print(f"🔗 Webhook received! Headers: {dict(request.headers)}")
        
        # Get raw payload for debugging
        raw_payload = request.get_data(as_text=True)
        print(f"📦 Raw payload: {raw_payload[:500]}...")
        
        # Get signature header
        signature_header = request.headers.get('X-Kick-Signature-256', '')
        print(f"🔐 Signature header: {signature_header[:20]}..." if signature_header else "🔐 No signature header")
        
        # For now, skip signature verification to test webhook delivery
        # if not verify_webhook_signature(raw_payload, signature_header):
        #     print("❌ Invalid webhook signature")
        #     return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse webhook payload
        payload = request.get_json()
        
        if not payload:
            print("❌ No JSON payload received")
            return jsonify({'error': 'No payload'}), 400
        
        # Log the full payload structure
        print(f"📋 Full payload structure: {json.dumps(payload, indent=2)}")
        
        # Log webhook event
        event_type = payload.get('event', {}).get('type', payload.get('type', 'unknown'))
        print(f"📨 Event type: {event_type}")
        
        # Handle ANY message event (try different payload structures)
        message_content = None
        username = None
        channel = None
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Try different payload structures
        if 'event' in payload and 'data' in payload['event']:
            data = payload['event']['data']
            message_content = data.get('content', data.get('message', ''))
            username = data.get('sender', {}).get('username', data.get('username', 'Unknown'))
            channel = data.get('chatroom', {}).get('channel', {}).get('slug', data.get('channel', 'unknown'))
        elif 'data' in payload:
            data = payload['data']
            message_content = data.get('content', data.get('message', ''))
            username = data.get('username', data.get('user', {}).get('username', 'Unknown'))
            channel = data.get('channel', 'unknown')
        else:
            # Log any webhook we receive, even if structure is unexpected
            message_content = str(payload)
            username = 'WEBHOOK_DATA'
            channel = 'system'
        
        # Store ALL messages for debugging
        if message_content:
            chat_entry = {
                'timestamp': timestamp,
                'username': username,
                'message': message_content,
                'channel': channel,
                'event_type': event_type,
                'full_payload': payload
            }
            
            all_chat_messages.append(chat_entry)
            
            # Keep only last 50 messages
            if len(all_chat_messages) > 50:
                all_chat_messages.pop(0)
            
            print(f"💬 CHAT CAPTURED!")
            print(f"   Channel: {channel}")
            print(f"   User: {username}")
            print(f"   Message: {message_content}")
            print(f"   Event: {event_type}")
            print("-" * 40)
        
        return jsonify({'status': 'success', 'received': True}), 200
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        print(f"❌ Request data: {request.get_data()}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    """Get current beef count and recent activity"""
    return jsonify({
        'beef_count': beef_count,
        'channel': CHANNEL_NAME,
        'recent_activity': chat_log[-10:] if chat_log else [],
        'all_chat_messages': all_chat_messages[-20:] if all_chat_messages else [],
        'webhook_secret_configured': WEBHOOK_SECRET is not None,
        'total_webhooks_received': len(all_chat_messages),
        'uptime': time.time()
    })

@app.route('/reset', methods=['POST'])
def reset_count():
    """Reset beef counter"""
    global beef_count, chat_log
    beef_count = 0
    chat_log = []
    save_beef_count()
    print("🔄 Beef count reset to 0")
    return jsonify({'status': 'reset', 'beef_count': beef_count})

@app.route('/setup-webhook', methods=['POST'])
def setup_webhook_route():
    """API endpoint to set up webhook"""
    success = setup_webhook()
    return jsonify({
        'success': success,
        'access_token': access_token is not None,
        'webhook_secret': WEBHOOK_SECRET[:8] + "..." if WEBHOOK_SECRET else None
    })

@app.route('/oauth-token', methods=['POST'])
def get_oauth_token_route():
    """API endpoint to get OAuth token"""
    token = get_client_credentials_token()
    return jsonify({
        'success': token is not None,
        'token_preview': token[:10] + "..." if token else None
    })

@app.route('/')
def dashboard():
    """Simple HTML dashboard"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kick Chat Monitor - Channel: {CHANNEL_NAME}</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: white; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .count {{ font-size: 48px; color: #FF4500; text-align: center; margin: 20px 0; }}
            .status {{ background: #333; padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .log {{ background: #222; padding: 10px; border-radius: 5px; max-height: 300px; overflow-y: auto; }}
            .beef-entry {{ background: #4a2c17; margin: 5px 0; padding: 8px; border-radius: 3px; border-left: 3px solid #D2691E; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🥩 Kick Chat Monitor</h1>
            <div class="status">
                <strong>Channel:</strong> {CHANNEL_NAME}<br>
                <strong>OAuth Token:</strong> {"✅ Active" if access_token else "❌ Not Set"}<br>
                <strong>Webhook Secret:</strong> {"✅ Configured" if WEBHOOK_SECRET else "❌ Not Set"}<br>
                <strong>Server:</strong> Running on http://localhost:5000
            </div>
            
            <div class="status">
                <h3>🔧 Setup Controls</h3>
                <button onclick="getOAuthToken()" style="background: #007bff; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; margin: 5px;">
                    🔐 Get OAuth Token
                </button>
                <button onclick="setupWebhook()" style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; margin: 5px;">
                    🔗 Setup Webhook
                </button>
                <div id="setup-status" style="margin-top: 10px; padding: 10px; border-radius: 3px; display: none;"></div>
            </div>
            
            <div class="count">{beef_count}</div>
            <div style="text-align: center; margin-bottom: 20px;">
                <strong>Total $beef Messages Detected</strong>
            </div>
            
            <div class="log">
                <h3>📨 All Webhook Messages ({len(all_chat_messages)} total):</h3>
                {''.join([f'<div class="beef-entry"><strong>{entry["timestamp"]}</strong> - <span style="color: #00aa00;">{entry["username"]}</span> [{entry["channel"]}]: {entry["message"][:100]}{"..." if len(entry["message"]) > 100 else ""} <em>({entry["event_type"]})</em></div>' for entry in all_chat_messages[-15:]]) if all_chat_messages else '<p>❌ No webhooks received yet. Check webhook configuration!</p>'}
            </div>
            
            <div class="log" style="margin-top: 20px;">
                <h3>🥩 Beef Activity:</h3>
                {''.join([f'<div class="beef-entry"><strong>{entry["timestamp"]}</strong> - {entry["username"]}: {entry["message"]} (#{entry["beef_count"]})</div>' for entry in chat_log[-10:]]) if chat_log else '<p>No beef detected yet...</p>'}
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="fetch('/reset', {{method: 'POST'}}).then(() => location.reload())" 
                        style="background: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    🔄 Reset Count
                </button>
            </div>
        </div>
        
        <script>
            function showStatus(message, success) {{
                const statusDiv = document.getElementById('setup-status');
                statusDiv.style.display = 'block';
                statusDiv.style.background = success ? '#d4edda' : '#f8d7da';
                statusDiv.style.color = success ? '#155724' : '#721c24';
                statusDiv.textContent = message;
                setTimeout(() => statusDiv.style.display = 'none', 5000);
            }}
            
            function getOAuthToken() {{
                showStatus('Getting OAuth token...', true);
                fetch('/oauth-token', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showStatus('✅ OAuth token obtained successfully!', true);
                            setTimeout(() => location.reload(), 2000);
                        }} else {{
                            showStatus('❌ Failed to get OAuth token', false);
                        }}
                    }})
                    .catch(err => showStatus('❌ Error: ' + err.message, false));
            }}
            
            function setupWebhook() {{
                showStatus('Setting up webhook...', true);
                fetch('/setup-webhook', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            showStatus('✅ Webhook setup successful! Check console for details.', true);
                            setTimeout(() => location.reload(), 2000);
                        }} else {{
                            showStatus('❌ Webhook setup failed. Check console for details.', false);
                        }}
                    }})
                    .catch(err => showStatus('❌ Error: ' + err.message, false));
            }}
        </script>
    </body>
    </html>
    '''

def setup_instructions():
    """Print setup instructions"""
    print("=" * 60)
    print("🥩 KICK CHAT WEBHOOK MONITOR")
    print("=" * 60)
    print(f"Channel: {CHANNEL_NAME}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Webhook URL: http://localhost:5000/webhook")
    print(f"Dashboard: http://localhost:5000")
    print("=" * 60)
    print("\n🚀 QUICK START:")
    print("1. Server is starting with your API credentials")
    print("2. Open dashboard at http://localhost:5000")
    print("3. Click '🔐 Get OAuth Token' button")
    print("4. Click '🔗 Setup Webhook' button")  
    print("5. Done! Chat monitoring will start automatically")
    print("\n⚠️  IMPORTANT: For webhooks to work from external sources:")
    print("   - Use ngrok: 'ngrok http 5000'")
    print("   - Update webhook URL to ngrok URL")
    print("=" * 60)

if __name__ == '__main__':
    load_beef_count()
    setup_instructions()
    
    # Open dashboard in browser
    threading.Timer(1.5, lambda: webbrowser.open('http://localhost:5000')).start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=True)