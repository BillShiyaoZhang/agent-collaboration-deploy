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
            if resp.status in [200, 201, 409]:
                return json.loads(content.decode("utf-8"))
            else:
                print(f"Request to {url} returned status {resp.status}: {content.decode('utf-8')}")
                return None
    except Exception as e:
        # Check if HTTPError (e.g. 409 which might be fine for contacts)
        if hasattr(e, 'code') and e.code == 409:
            try:
                return json.loads(e.read().decode("utf-8"))
            except:
                pass
        print(f"Error requesting {url}: {e}")
        return None

def login():
    # 1. Get CSRF token
    csrf_data = api_request(f"{CLOUD_BASE}/api/auth/csrf")
    if not csrf_data or "csrfToken" not in csrf_data:
        print("Failed to get CSRF token")
        return False
    csrf_token = csrf_data["csrfToken"]
    
    # 2. POST credentials
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
            print(f"Session cookies obtained: {cookies}")
            return any("session-token" in name for name in cookies)
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def get_local_agent_info():
    req = urllib.request.Request(f"{LOCAL_BASE}/info")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed to fetch local daemon info from {LOCAL_BASE}/info: {e}")
    return None

def main():
    print("=== Step 1: Checking local agent daemon ===")
    info = get_local_agent_info()
    if not info:
        print("Error: Local agent-comm-helper daemon is not running!")
        sys.exit(1)
    
    agent_urn = info["urn"]
    print(f"Local agent URN: {agent_urn}")
    
    print("\n=== Step 2: Logging in to Cloud Dashboard ===")
    if not login():
        print("Error: Cloud login failed!")
        sys.exit(1)
    print("Login successful.")

    print("\n=== Step 3: Binding Local Agent to Cloud Account ===")
    existing_agents = api_request(f"{CLOUD_BASE}/api/agents")
    agent_id = None
    if existing_agents:
        for a in existing_agents:
            if a["urn"] == agent_urn:
                print(f"Agent {agent_urn} already bound to account with ID: {a['id']}")
                agent_id = a["id"]
                break
    
    if not agent_id:
        bind_data = {
            "mode": "bind",
            "name": "Local Hermes Agent",
            "urn": agent_urn,
            "localUrl": LOCAL_BASE
        }
        res = api_request(f"{CLOUD_BASE}/api/agents", method="POST", data=bind_data)
        if not res or "id" not in res:
            print("Error: Failed to bind agent on cloud!")
            sys.exit(1)
        agent_id = res["id"]
        print(f"Agent successfully bound. Cloud ID: {agent_id}")

    print("\n=== Step 4: Establishing Mutual Trust ===")
    trust_res = api_request(f"{CLOUD_BASE}/api/agents/{agent_id}/bind-owner", method="POST")
    if not trust_res or "virtualUrn" not in trust_res:
        print("Error: Failed to fetch owner virtual identity from cloud!")
        sys.exit(1)
    
    owner_urn = trust_res["virtualUrn"]
    owner_ed_pk = trust_res["virtualEd25519PublicKey"]
    owner_x_pk = trust_res["virtualX25519PublicKey"]
    print(f"Cloud Owner Virtual URN: {owner_urn}")

    local_contact_payload = {
        "contact_urn": owner_urn,
        "alias": "Owner (Cloud Console)",
        "trust_tier": "self",
        "ed25519_public_key": owner_ed_pk,
        "x25519_public_key": owner_x_pk
    }
    
    local_push_res = api_request(f"{LOCAL_BASE}/contacts", method="POST", data=local_contact_payload)
    if not local_push_res or not local_push_res.get("success"):
        print("Error: Failed to push Owner identity to local agent contacts database!")
        sys.exit(1)
    print("Owner identity successfully injected into local agent contacts.")

    cloud_contact_payload = {
        "agentId": agent_id,
        "contactUrn": owner_urn,
        "trustTier": "self",
        "alias": "Owner (Cloud Console)",
        "publicKey": owner_ed_pk
    }
    
    api_request(f"{CLOUD_BASE}/api/contacts", method="POST", data=cloud_contact_payload)
    print("Trust state synchronized with Cloud database.")

    print("\n=== Step 5: Syncing Platform Registry Status ===")
    sync_res = api_request(f"{CLOUD_BASE}/api/agents/{agent_id}/register", method="POST")
    if sync_res:
        print(f"Sync complete. Platform Registered: {sync_res.get('platformRegistered')}")
    else:
        print("Warning: Sync status request failed, proceeding anyway...")

    print("\n=== E2E Trust Binding Setup Completed Successfully! ===")

if __name__ == "__main__":
    main()
