# -*- coding: utf-8 -*-
"""
Feishu Integration Module - Supports running as independent thread
"""
import os
import json
import requests
import time
import threading
import queue
from flask import Flask, request, jsonify

app = Flask(__name__)
feishu_config = None
_agent_instance = None
_access_token = None
_token_expire = 0
_processed_messages = {}
_flask_thread = None
_is_running = False

def init_feishu(config):
    """Initialize Feishu configuration"""
    global feishu_config
    feishu_config = config
    print(f"✅ Feishu configuration initialized: APP_ID={config.get('APP_ID', 'not configured')}")

def set_agent(agent):
    """Set Agent instance"""
    global _agent_instance
    _agent_instance = agent

def get_agent():
    """Get Agent instance"""
    global _agent_instance
    return _agent_instance

def get_tenant_access_token():
    """Get Feishu tenant access token"""
    global _access_token, _token_expire
    
    if not feishu_config:
        print("❌ Feishu configuration not initialized")
        return None
        
    if _access_token and time.time() < _token_expire:
        return _access_token
    
    app_id = feishu_config.get('APP_ID')
    app_secret = feishu_config.get('APP_SECRET')
    
    if not app_id or not app_secret:
        print("❌ Feishu APP_ID or APP_SECRET not configured")
        return None
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": app_id, "app_secret": app_secret}
    
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            _access_token = data.get("tenant_access_token")
            _token_expire = time.time() + data.get("expire", 7200) - 60
            print(f"✅ Feishu token obtained successfully, expiration time: {time.ctime(_token_expire)}")
            return _access_token
        else:
            print(f"❌ Failed to get Feishu token: HTTP {resp.status_code}, response: {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Exception while getting Feishu token: {e}")
        return None

def is_duplicate_message(message_id):
    """Check if message is duplicate"""
    global _processed_messages
    now = time.time()
    
    expired = [mid for mid, ts in _processed_messages.items() if now - ts > 60]
    for mid in expired:
        del _processed_messages[mid]
    
    if message_id in _processed_messages:
        return True
    
    _processed_messages[message_id] = now
    return False

def send_feishu_message(open_id, text):
    """Send Feishu message"""
    if not text:
        print("[Warning] Attempting to send empty message")
        return {"success": False, "error": "Message content is empty"}

    token = get_tenant_access_token()
    if not token:
        return {"success": False, "error": "Failed to get token"}

    send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {"receive_id_type": "open_id"}

    send_data = {
        "receive_id": open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }

    try:
        send_resp = requests.post(send_url, headers=headers, params=params, json=send_data, timeout=10)
        resp_json = send_resp.json()

        if send_resp.status_code == 200 and resp_json.get("code") == 0: 
            message_id = resp_json.get("data", {}).get("message_id") 
            if message_id: 
                global _processed_messages 
                _processed_messages[message_id] = time.time() 
            print(f"✅ Message sent successfully to {open_id}") 
            return {"success": True}
        else:
            print(f"❌ Feishu API returned error: HTTP {send_resp.status_code}, Body: {resp_json}")
            return {"success": False, "error": resp_json}
    except Exception as e:
        print(f"❌ Exception during send request: {e}")
        return {"success": False, "error": str(e)}

@app.route('/webhook/feishu', methods=['POST'])
def webhook():
    raw_data = request.get_json()
    print(f"📥 [RAW] Complete request data: {raw_data}")
    
    try:
        data = raw_data
        
        msg_type = data.get("type") 
        if not msg_type:
            header = data.get("header", {})
            msg_type = header.get("event_type")
        
        print(f"🏷️ [EVENT_TYPE] Event type identified: {msg_type}")

        if msg_type == "url_verification":
            challenge = data.get("challenge")
            print(f"✅ [CHALLENGE] Received verification request, returning: {challenge}")
            return jsonify({"challenge": challenge})
        
        if msg_type == "im.message.receive_v1":
            event = data.get("event", {})
            message = event.get("message", {})
            my_app_id = feishu_config.get('APP_ID') if feishu_config else None
            if my_app_id and message.get('app_id') == my_app_id:
                print("⏭️ [SKIP] Ignoring message sent by bot itself (app_id match)")
                return jsonify({"code": 0})
        
        if feishu_config and feishu_config.get('VERIFICATION_TOKEN'):
            token = feishu_config.get('VERIFICATION_TOKEN')
            signature = request.headers.get('X-Lark-Signature')
            print(f"🔒 [VERIFY] Verifying Token: {token}, Signature: {signature}")
        
        if msg_type == "im.message.receive_v1":
            print("🚀 [INFO] Message event detected, starting parsing...")
            event = data.get("event")
            if not event:
                print("❌ [ERROR] Missing 'event' field")
                return jsonify({"code": 0})
            
            message = event.get("message", {})
            sender = event.get("sender", {})
            message_id = message.get("message_id")
            content_raw = message.get("content")
            sender_open_id = sender.get("sender_id", {}).get("open_id")
            user_name = sender.get("sender_name", "UnknownUser")
            
            print(f"📝 [DEBUG] message_id: {message_id}, content_raw: {content_raw}")
            print(f"👤 [DEBUG] sender_open_id: {sender_open_id}, user_name: {user_name}")
            
            if not message_id:
                print("❌ [ERROR] Missing message_id")
                return jsonify({"code": 0})
                
            if is_duplicate_message(message_id):
                print(f"⏭️ [SKIP] Message already processed (duplicate): {message_id}")
                return jsonify({"code": 0})
            
            text = ""
            try:
                if content_raw:
                    content_json = json.loads(content_raw)
                    text = content_json.get("text", "")
                    print(f"📝 [DEBUG] Parsed text: {text}")
            except Exception as e:
                print(f"⚠️ [WARN] Failed to parse content: {e}")
            
            if not text or not text.strip():
                print("⏭️ [SKIP] Empty message content")
                return jsonify({"code": 0})

            print(f"👤 [RECV] User: {user_name} | Content: {text}")
            
            agent = get_agent()
            print(f"🤖 [DEBUG] Agent object: {agent}")
            reply_text = "System busy, please try again later."
            
            try:
                print("⚙️ [PROC] Calling Agent...")
                result_dict = agent.handle_message(sender_open_id, text, priority="normal")
                
                if isinstance(result_dict, dict):
                    reply_text = result_dict.get("reply") or result_dict.get("message") or result_dict.get("result") or "Command received."
                else:
                    reply_text = str(result_dict)
                
                if len(reply_text) > 4000:
                    reply_text = reply_text[:4000] + "\n...(truncated)"
                    
                print(f"🤖 [REPLY] Generated reply: {reply_text[:50]}...")
                
                if sender_open_id:
                    send_res = send_feishu_message(sender_open_id, reply_text)
                    if send_res.get("success"):
                        print("✅ [SUCCESS] Message sent to Feishu successfully!")
                    else:
                        print(f"❌ [FAIL] Send API error: {send_res.get('error')}")
                else:
                    print("❌ [FAIL] Cannot get sender_open_id")
                    
            except Exception as e:
                print(f"💥 [CRASH] Agent processing exception: {e}")
                import traceback
                traceback.print_exc()
                if sender_open_id:
                    send_feishu_message(sender_open_id, f"😭 Bot error: {str(e)}")
                    
            return jsonify({"code": 0})
        else:
            if msg_type:
                print(f"ℹ️ [INFO] Ignoring other event types: {msg_type}")
            else:
                print(f"⚠️ [WARN] Received request with unknown format, no event_type: {data.keys()}")

            return jsonify({"code": 0})
    except Exception as e:
        print(f"❌ [ERROR] Exception during request processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500})

def start_feishu_service():
    """Start Feishu service"""
    global _flask_thread, _is_running
    
    if _is_running:
        print("⚠️ Feishu service already running")
        return
        
    _is_running = True
    
    def run_flask():
        """Run Flask in separate thread"""
        try:
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            print("🚀 Flask service started successfully, listening on all network interfaces")
        except Exception as e:
            print(f"❌ Flask service exception: {e}")
        finally:
            global _is_running
            _is_running = False
    
    _flask_thread = threading.Thread(target=run_flask, daemon=True)
    _flask_thread.start()
    print("🚀 Feishu service started, listening on port 5000")

def stop_feishu_service():
    """Stop Feishu service"""
    global _flask_thread, _is_running
    
    if not _is_running:
        print("⚠️ Feishu service not running")
        return
        
    _is_running = False
    print("🛑 Feishu service stopped")

if __name__ == "__main__":
    start_feishu_service()
    print("Press Ctrl+C to stop service")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_feishu_service()
        print("Service stopped")
