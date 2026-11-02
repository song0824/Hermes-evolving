import socket, json, os, glob

# Find the hermes_rpc socket
socks = glob.glob("/tmp/hermes_rpc_*.sock")
print(f"Found sockets: {socks}")

for sock_path in socks:
    print(f"\nTrying: {sock_path}")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(sock_path)
        print("Connected!")
        # Try ping
        req = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "list_db_connections"}, "id": 1}
        sock.sendall(json.dumps(req).encode() + b"\n")
        
        data = b""
        sock.settimeout(10)
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        
        print("Response:", data.decode()[:2000])
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
