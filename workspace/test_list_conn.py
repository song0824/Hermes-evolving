import socket
import json
import tempfile
import os

socket_path = os.path.join(tempfile.gettempdir(), "hermes-rds-daemon.sock")

# Read auth token
with open("/root/.hermes/rds/.daemon-token") as f:
    token = f.read().strip()

# Try list_connections (doesn't require registration)
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(10)
try:
    sock.connect(socket_path)
    
    req = {"action": "list_connections", "auth_token": token}
    sock.sendall(json.dumps(req).encode() + b"\n")
    
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
        if b"\n" in data:
            break
    
    resp = json.loads(data.split(b"\n")[0])
    print("list_connections response:")
    print(json.dumps(resp, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
finally:
    sock.close()
