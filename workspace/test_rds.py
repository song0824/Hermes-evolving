import socket
import json

# Try to connect to the RDS daemon
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    sock.connect('/tmp/hermes-rds-daemon.sock')
    print("Connected to daemon!")
    
    # Send a query request
    query = {
        "method": "query",
        "connection_id": "lingos_new",
        "sql": "SELECT 1 as test"
    }
    sock.sendall(json.dumps(query).encode() + b"\n")
    
    # Read response
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    
    print("Response:", data.decode())
except Exception as e:
    print(f"Error: {e}")
finally:
    sock.close()
