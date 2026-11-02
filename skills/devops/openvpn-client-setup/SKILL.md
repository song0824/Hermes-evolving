---
name: openvpn-client-setup
description: Connect to OpenVPN servers from modern Linux (Ubuntu 22.04+/OpenSSL 3.0+). Covers legacy server compatibility, encrypted key handling, OpenSSL 3.0 TLS workarounds, and systematic connection debugging.
---

# OpenVPN Client Setup on Modern Linux

## When to Use
- User provides an `.ovpn` config file and needs to connect from a Linux server
- OpenVPN connection fails with TLS or authentication errors on Ubuntu 22.04+/OpenSSL 3.0+
- Connecting to legacy OpenVPN servers (2.3.x/2.4.x era) from modern clients

## Prerequisites
```bash
apt-get install -y openvpn expect
```

## Setup Steps

### 1. Extract and Verify Config Files
Unzip the provided archive. A standard OpenVPN client config references:
- `.ovpn` config file
- `ca.crt` — CA certificate
- `client.crt` — Client certificate
- `client.key` — Client private key (may be encrypted)

### 2. Handle Encrypted Private Keys
If the `.key` file starts with `-----BEGIN ENCRYPTED PRIVATE KEY-----`, it needs a password.

Test the password:
```bash
openssl rsa -in vpnclient.key -passin pass:'YOUR_PASSWORD' -check 2>&1 | head -5
```

Decrypt for OpenVPN use:
```bash
openssl rsa -in vpnclient.key -passin pass:'YOUR_PASSWORD' -out vpnclient_decrypted.key
chmod 600 vpnclient_decrypted.key
```

Update the `.ovpn` to reference the decrypted key:
```
key vpnclient_decrypted.key
```

### 3. Create Auth File
If the server requires username/password:
```bash
printf 'username\npassword\n' > auth.txt
chmod 600 auth.txt
```
Add to config: `auth-user-pass /absolute/path/to/auth.txt`

### 4. OpenSSL 3.0 Compatibility (Critical for Legacy Servers)
OpenVPN 2.6+ uses OpenSSL 3.0, which blocks legacy TLS algorithms by default. Legacy OpenVPN servers (2.3.x era) will fail with `legacy sigalg disallowed` or TLS errors.

**Fix**: Create a custom OpenSSL config that enables the legacy provider and relaxes security:

```ini
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect

[provider_sect]
default = default_sect
legacy = legacy_sect

[default_sect]
activate = 1

[legacy_sect]
activate = 1

[system_default_sect]
CipherString = DEFAULT:@SECLEVEL=0
MinProtocol = TLSv1
SignatureAlgorithms = RSA-PSS+SHA256:RSA-PSS+SHA384:RSA-PSS+SHA512:RSA+SHA256:RSA+SHA384:RSA+SHA512:RSA+SHA224:RSA+SHA1:ECDSA+SHA256:ECDSA+SHA384:ECDSA+SHA512:ECDSA+SHA224:ECDSA+SHA1
```

Launch with: `OPENSSL_CONF=/path/to/openssl.cnf openvpn --config client.ovpn`

A ready-to-use OpenSSL legacy config is available at `templates/openssl-legacy.cnf`.

### 5. Compatible Config Template
```
client
dev tun
proto tcp
remote SERVER_IP PORT
resolv-retry infinite
nobind
persist-key
persist-tun
ca ca.crt
cert client.crt
key client_decrypted.key
remote-cert-tls server
verb 3
data-ciphers AES-256-CBC:AES-128-CBC
data-ciphers-fallback AES-256-CBC
auth SHA1
auth-user-pass /absolute/path/to/auth.txt
tls-version-min 1.0
tls-cipher "TLS-RSA-WITH-AES-256-CBC-SHA:TLS-RSA-WITH-AES-128-CBC-SHA"
comp-lzo
allow-compression yes
```

### 6. Important Flags
- Use `--cd /path/to/config/dir` so relative cert paths resolve correctly
- Or use absolute paths for all cert/key files
- Use `--daemon --log /tmp/openvpn.log` for background mode
- `expect` can be used if interactive auth prompts appear

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed retrieving username or password` | auth-user-pass file not found, wrong permissions, or systemd ask-password interference | Use absolute path, `chmod 600`, ensure file has trailing newline |
| `legacy sigalg disallowed or unsupported` | OpenSSL 3.0 blocks old signature algorithms | Use custom `OPENSSL_CONF` with legacy provider + SECLEVEL=0 |
| `Cipher BF-CBC not supported` | OpenSSL 3.0 removed BF-CBC from default ciphers | Use `data-ciphers-fallback AES-256-CBC` instead |
| `Unsupported protocol` (TLS) | Server only supports TLS 1.0/1.1 | Add `tls-version-min 1.0` |
| `Connection reset` after TLS VERIFY OK | Server-side incompatibility with OpenVPN 2.6 control channel | Try older cipher suites, or install OpenVPN 2.4/2.5 with OpenSSL 1.1 |
| `No such file or directory` for certs | Running from wrong working directory | Use `--cd /config/dir` or absolute paths |

## Pitfalls
- **Port 10080 is ERR_UNSAFE_PORT in browser**: Chrome/Playwright blocks port 10080. Use `curl -H "Host: domain" http://INTERNAL_IP:10080/path` via terminal instead.
- OpenVPN 2.6+ with OpenSSL 3.0 is **incompatible** with very old OpenVPN servers (pre-2.4). If TLS handshake succeeds (VERIFY OK) but server immediately resets, the server is likely too old. Consider installing OpenVPN 2.5 from source or using a container with OpenSSL 1.1.
- The `comp-lzo` directive is deprecated in OpenVPN 2.6; use `allow-compression yes` alongside it.
- Always test the OpenSSL config with `openssl list -providers` before running OpenVPN — both `default` and `legacy` should show `status: active`.
- Systemd's `systemd-ask-password` mechanism can interfere with OpenVPN auth file reading in containers/minimal environments. Always verify the auth file is being read correctly.
- OpenSSL 3.0 removed BF-CBC cipher. Legacy configs using `data-ciphers-fallback BF-CBC` will fail — replace with `AES-256-CBC`.

---

## Sub-section: VPN Tunnel Use Case (from vpn-tunnel)
When you need to route browser traffic through a VPN to bypass IP restrictions (e.g., 抖店 2046 error):
1. Follow the setup steps above to connect OpenVPN
2. Verify tunnel: `ip addr show tun0`, `ip route show | grep tun0`
3. Test exit IP: `curl -s --interface tun0 http://httpbin.org/ip`
4. MTU issues: if ping works but HTTP times out, try `ip link set tun0 mtu 1300`
5. Keep VPN as daemon: `openvpn --cd /path --config working.ovpn --daemon --log /tmp/openvpn.log`
- Session-specific server config: see `references/yuzhe-vpn-server.md`

## Sub-section: systemd-ask-password Workaround (from openvpn-linux-troubleshoot)
When `Failed retrieving username or password` occurs despite valid auth-user-pass file:
- OpenVPN 2.6+ on Ubuntu 24.04 tries `systemd-ask-password` even with file path
- Workaround: create shim at `/usr/local/bin/systemd-ask-password` that echoes credentials
- Or use `strace -f -e trace=open,openat,read -o /tmp/ovpn_strace.log openvpn --config client.ovpn` to diagnose
- See `references/openssl3-compat.md` for OpenSSL 3.0 compatibility details

## Sub-section: Legacy Server Connection (from openvpn-legacy-server-connect)
For servers using BF-CBC, SHA1, TLSv1 (OpenVPN 2.3.x era):
- THE key directive: `tls-cert-profile insecure` — allows SHA1 certificate signatures
- Also needed: `tls-version-min 1.0`, `compat-mode 2.4.0`, `cipher BF-CBC`, `data-ciphers BF-CBC`
- Don't use custom OpenSSL config files — `tls-cert-profile insecure` is simpler and sufficient
- See `references/legacy-troubleshooting.md` for failed approaches to avoid

## Sub-section: Internal Service Discovery via VPN Tunnel
After connecting, internal services may not be directly reachable via their DNS names (DNS resolves to public IP). Use `references/internal-service-discovery.md` for the systematic discovery procedure:
- Scan routed subnets (from `ip route | grep tun0`) for the service port
- Check the VPN gateway (10.8.0.1) for common ports (80/22/443/8080/10080)
- Try Host header override on gateway HTTP service
- If no port found: service may be down, on non-routed subnet, or behind firewall