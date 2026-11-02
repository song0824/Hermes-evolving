# Internal Service Discovery via VPN Tunnel

When connected to a VPN tunnel, internal services may not be directly accessible via their DNS names. Common pattern:

## Problem
- DNS resolves `internal-service.company.com` to the **public IP** (e.g. 114.242.33.251)
- Even with VPN active, the public IP + service port times out
- Service may be on a different internal IP only reachable via VPN

## Discovery Procedure

### Step 1: Confirm VPN is up
```bash
ip addr show tun0          # Should show 10.8.0.x
ip route | grep tun0       # Shows routed subnets
```

### Step 2: Check DNS resolution
```bash
getent hosts service-name.company.com
# or
python3 -c "import socket; print(socket.getaddrinfo('service-name.company.com', None))"
```
If it resolves to the **public IP** (same as the VPN server), the service likely needs a different access path.

### Step 3: Scan routed subnets
Use the subnets from `ip route | grep tun0` to discover the service:
```python
import socket, concurrent.futures

def check_port(ip, port, timeout=2):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    result = s.connect_ex((ip, port))
    s.close()
    return ip if result == 0 else None

# Scan all routed subnets (example: 10.0.0.0/24, 10.0.4.0/24, etc.)
ips = [f"10.0.0.{i}" for i in range(1, 255)]  # extend for each subnet
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
    futs = {ex.submit(check_port, ip, TARGET_PORT, 2): ip for ip in ips}
    for f in concurrent.futures.as_completed(futs):
        r = f.result()
        if r: print(f"Found: {r}:{TARGET_PORT}")
```

### Step 4: Check VPN gateway
The VPN gateway (usually 10.8.0.1 or the peer IP) may proxy or host the service:
```bash
# Scan common ports on gateway
for port in 80 443 3000 8080 8443 10080; do
    nc -zv 10.8.0.1 $port -w 2 2>&1
done
```

### Step 5: Try Host header override
If you find an HTTP service on the gateway:
```bash
curl -H "Host: service-name.company.com" http://10.8.0.1/path
```

## Pitfalls
- **Browser blocks port 10080**: Chrome/Playwright returns `ERR_UNSAFE_PORT` for ports like 10080. Use `curl` or Python `requests` via terminal instead. This is a Chromium hardcoded blocklist, not a network issue.
- **DNS resolves to public IP even with VPN active**: The domain `gitlab.ling.ai` resolves to `114.242.33.251` (public). Even with VPN, curl to that IP times out. Must use the **internal IP** (e.g. `10.0.12.213:10080`) directly.
- **Host header required**: When using internal IP, pass `-H "Host: gitlab.ling.ai"` (or the service's domain) — otherwise the backend may not route correctly.

## Example: GitLab internal access (ling.ai)
- DNS: `gitlab.ling.ai` → `114.242.33.251` (public, times out)
- Internal: `10.0.12.213:10080` (found via subnet scan of 10.0.12.0/24)
- Access: `curl -H "Host: gitlab.ling.ai" http://10.0.12.213:10080/...`
- Auth: Returns redirect to `/users/sign_in` — needs Personal Access Token or cookie auth
- Browser: `browser_navigate` fails with `ERR_UNSAFE_PORT` on 10080 — use terminal curl only

## Common patterns found
- **10.8.0.1** (VPN gateway): Often has port 80/22 open — may be a reverse proxy or management interface
- **10.0.x.x subnets**: Application servers (GitLab, databases, etc.)
- If **no port found** on expected IP: The service may be down, on a non-routed subnet, or behind NAT/firewall rules
