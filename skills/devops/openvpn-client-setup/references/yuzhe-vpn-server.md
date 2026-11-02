## VPN Server Details (yuzhe)

**Server**: `114.242.33.251:30000` (TCP)
**User**: `yuzhe`
**Password**: `yuzhe@ling.space`
**Key Passphrase**: `yuzhe@ling.space`

### Files Location
- Config: `/root/.hermes/cache/config/working.ovpn`
- Certs: `/root/.hermes/cache/config/ca.crt`, `vpnclient.crt`, `vpnclient_decrypted.key`
- OpenSSL: `/root/.hermes/cache/config/openssl.cnf`
- Auth: `/root/.hermes/cache/config/auth.txt`

### Connection Command
```bash
OPENSSL_CONF=/root/.hermes/cache/config/openssl.cnf openvpn --cd /root/.hermes/cache/config --config /root/.hermes/cache/config/working.ovpn --daemon --log /tmp/openvpn.log
```

### Network After Connect
- VPN IP: `10.8.0.42` (peer: `10.8.0.41`)
- Exit IP: `114.242.33.251` (residential)
- Internal routes: `10.0.0.0/24`, `10.0.4.0/24`, `10.0.5.0/24`, `10.0.12.0/24`
- Default route via tun0 (split tunnel: `0.0.0.0/1` + `128.0.0.0/1`)

### Use Case
Used to bypass 抖店 (fxg.jinritemai.com) 2046 IP-based anti-bot restriction.
With VPN active, browser can access 抖店 login page and generate QR codes normally.
