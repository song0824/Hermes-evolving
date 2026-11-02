# OpenVPN Legacy Server Troubleshooting Notes

## Server Profile (lingwu OpenVPN)
- Server: 114.242.33.251:30000 (TCP only)
- Server version: ~OpenVPN 2.3.x era
- TLS: TLSv1, cipher DHE-RSA-AES256-SHA
- Data channel: BF-CBC with SHA1 HMAC
- Certificate signatures: SHA1
- Auth: username/password + client certificate
- VPN subnet: 10.8.0.0/24
- Pushes routes: 10.0.0.0/24, 10.0.4.0/24, 10.0.5.0/24, 10.0.12.0/24

## Failed Approaches (Do Not Repeat)
1. **Custom OpenSSL config with legacy provider** — Did NOT resolve `legacy sigalg disallowed`. The fix is `tls-cert-profile insecure` in the OpenVPN config.
2. **`data-ciphers-fallback BF-CBC` alone** — Insufficient. Need full set: `cipher BF-CBC`, `data-ciphers BF-CBC`, `data-ciphers-fallback BF-CBC`, `compat-mode 2.4.0`.
3. **`tls-cipher` overrides** — Setting explicit TLS cipher didn't help; issue was cert signature validation.
4. **UDP protocol** — This server is TCP-only. UDP gives `ECONNREFUSED`.
5. **OpenVPN 2.5 compilation** — Timed out. Not needed; 2.6 works with correct flags.

## Key Lessons
- Working Mac client uses OpenVPN 2.4.12 with OpenSSL 1.1.1 — no SHA1 restrictions
- Issue is OpenSSL 3.0 + OpenVPN 2.6 security hardening, not server incompatibility
- `tls-cert-profile insecure` is THE key directive, not custom OpenSSL configs
