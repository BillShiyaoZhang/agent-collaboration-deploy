import urllib.request
import urllib.parse
import json
import time
import http.cookiejar
import sys

CLOUD_BASE = "http://8.130.40.38"
LOCAL_BASE = "http://127.0.0.1:45042"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
urllib.request.install_opener(opener)

def api_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            if resp.status in [200, 201]:
                return json.loads(content.decode("utf-8"))
            else:
                print(f"Request to {url} returned status {resp.status}: {content.decode('utf-8')}")
                return None
    except Exception as e:
        print(f"Error requesting {url}: {e}")
        return None

def login():
    csrf_data = api_request(f"{CLOUD_BASE}/api/auth/csrf")
    if not csrf_data or "csrfToken" not in csrf_data:
        print("Failed to get CSRF token")
        return False
    csrf_token = csrf_data["csrfToken"]
    
    login_url = f"{CLOUD_BASE}/api/auth/callback/credentials"
    login_data = {
        "csrfToken": csrf_token,
        "email": "test@example.com",
        "password": "testadmin",
        "json": "true"
    }
    login_bytes = urllib.parse.urlencode(login_data).encode("utf-8")
    req = urllib.request.Request(
        login_url,
        data=login_bytes,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            cookies = [cookie.name for cookie in cj]
            return any("session-token" in name for name in cookies)
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def get_local_agent_urn():
    req = urllib.request.Request(f"{LOCAL_BASE}/info")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data["urn"]
    except Exception as e:
        print(f"Failed to fetch local daemon info: {e}")
    return None

def main():
    print("=== Step 1: Logging in to Cloud Dashboard ===")
    if not login():
        print("Error: Cloud login failed!")
        sys.exit(1)
    print("Login successful.")

    print("\n=== Step 2: Fetching Agent details ===")
    agent_urn = get_local_agent_urn()
    if not agent_urn:
        print("Error: Local agent daemon is not running!")
        sys.exit(1)
    
    existing_agents = api_request(f"{CLOUD_BASE}/api/agents")
    agent_id = None
    if existing_agents:
        for a in existing_agents:
            if a["urn"] == agent_urn:
                agent_id = a["id"]
                break
    
    if not agent_id:
        print(f"Error: Agent with URN {agent_urn} is not registered/bound in the cloud database!")
        sys.exit(1)
    print(f"Target Agent ID: {agent_id}, URN: {agent_urn}")

    # Send E2E message to Agent
    print("\n=== Step 3: Sending Message from Owner to Local Agent ===")
    msg_content = "Ping from cloud owner! Please reply with your status."
    send_payload = {
        "agentId": agent_id,
        "recipientUrn": agent_urn,
        "content": msg_content
    }
    
    res = api_request(f"{CLOUD_BASE}/api/messages", method="POST", data=send_payload)
    if not res:
        print("Error: Failed to send message to Agent!")
        sys.exit(1)
    print("Message successfully sent via E2E console to MQ platform.")

    print("\n=== Step 4: Polling for Agent Reply ===")
    print("We will poll the cloud messages database for any incoming replies from the agent...")
    reply_found = False
    
    for i in range(12):
        print(f"Polling check {i+1}/12...")
        messages = api_request(f"{CLOUD_BASE}/api/messages?agentId={agent_id}&contactUrn={urllib.parse.quote(agent_urn)}")
        if messages:
            incoming = [m for m in messages if m.get("isIncoming") == True]
            if incoming:
                print("\n=== Found replies from Agent! ===")
                for msg in incoming:
                    print(f"[{msg['createdAt']}] {msg['senderUrn']}: {msg['content']}")
                reply_found = True
                break
        time.sleep(5)

    if not reply_found:
        print("\nError: Timed out waiting for Agent reply! Please inspect debug logs.")
        sys.exit(1)
        
    print("\n=== E2E Communication Test Completed Successfully! ===")

if __name__ == "__main__":
    main()
