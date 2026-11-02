import sys
import os

# Add the plugin to path
plugin_dir = "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages"
sys.path.insert(0, plugin_dir)

from rds_security_plugin.daemon_client import DaemonClient, get_socket_path, _get_auth_token

import json
import socket
import tempfile

socket_path = os.path.join(tempfile.gettempdir(), "hermes-rds-daemon.sock")
print(f"Socket path: {socket_path}")
print(f"Socket exists: {os.path.exists(socket_path)}")

token = _get_auth_token()
print(f"Auth token: {token}")

# Step 1: Register caller
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(10)
try:
    sock.connect(socket_path)
    
    # Register
    reg_req = {"action": "register_caller", "auth_token": token}
    sock.sendall(json.dumps(reg_req).encode() + b"\n")
    
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
        for line in data.split(b"\n"):
            line = line.strip()
            if line:
                print("Register response:", json.loads(line))
                break
        if b"\n" in data:
            break
    
    # Step 2: Execute SQL
    sock2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock2.settimeout(30)
    sock2.connect(socket_path)
    
    sql_req = {
        "action": "execute_sql",
        "connection_id": "lingos_new",
        "sql": "SELECT 1 as test",
        "params": {},
        "auth_token": token
    }
    sock2.sendall(json.dumps(sql_req).encode() + b"\n")
    
    data = b""
    while True:
        chunk = sock2.recv(65536)
        if not chunk:
            break
        data += chunk
        for line in data.split(b"\n"):
            line = line.strip()
            if line:
                resp = json.loads(line)
                print("SQL response:", json.dumps(resp, ensure_ascii=False, indent=2)[:2000])
                break
        if b"\n" in data:
            break
    
    sock2.close()
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
finally:
    sock.close()
