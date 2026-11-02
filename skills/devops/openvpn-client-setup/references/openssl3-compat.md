# OpenSSL 3.0 Compatibility with OpenVPN

## Problem
OpenSSL 3.0 (Ubuntu 24.04+) changed default security policies:
- Removed BF-CBC (Blowfish) from default provider
- TLS 1.0/1.1 disabled by default (`tls-version-min 1.2`)
- Legacy algorithms moved to separate provider

## Workaround 1: Enable legacy provider in OpenSSL config

```bash
# Find OpenSSL config
openssl version -d  # e.g. OPENSSLDIR: "/usr/lib/ssl"
# Config is at /usr/lib/ssl/openssl.cnf

# Edit to add legacy provider
# Under [openssl_init] section, add:
providers = provider_sect

# Add section:
[provider_sect]
default = default_sect
legacy = legacy_sect

[default_sect]
activate = 1

[legacy_sect]
activate = 1
```

Then BF-CBC becomes available for `data-ciphers-fallback BF-CBC`.

## Workaround 2: TLS version min override

Add to OpenVPN config:
```
tls-version-min 1.0
```

If the server still rejects, the OpenSSL system-level security level may block it:
```bash
# Check current level
grep -i "SECLEVEL" /usr/lib/ssl/openssl.cnf

# Lower to level 0 (allows TLS 1.0, weak ciphers)
# Change: CipherString = DEFAULT:@SECLEVEL=2
# To:     CipherString = DEFAULT:@SECLEVEL=0
```

## Diagnostic commands

```bash
# Check if BF-CBC is available
openssl ciphers -v | grep BF-CBC

# Test TLS connection manually
openssl s_client -connect SERVER:PORT -tls1 -brief 2>&1
openssl s_client -connect SERVER:PORT -tls1_1 -brief 2>&1
openssl s_client -connect SERVER:PORT -tls1_2 -brief 2>&1

# Check OpenSSL version and providers
openssl version
openssl list -providers
```
