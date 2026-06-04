---
name: kernel-proxies
description: Create and manage datacenter, ISP, residential, mobile, and custom proxies for Kernel browsers.
---

# Proxies

Use proxies to route browser traffic through specific networks for geography,
privacy, testing, or bot-detection constraints.

Creating, changing, or deleting proxies can affect active browser behavior, so
confirm user intent before mutating existing proxies.

## Types

- `datacenter` - fastest commercial data-center traffic.
- `isp` - data-center routed traffic using ISP-assigned residential IPs.
- `residential` - real residential IPs, usually least detectable.
- `mobile` - mobile carrier networks.
- `custom` - user-provided proxy servers.

## Create

```bash
kernel proxies create --type datacenter --country US --name "US DC" -o json
kernel proxies create --type isp --country US --name "US ISP" -o json
kernel proxies create --type residential --country US --city sanfrancisco --state CA -o json
kernel proxies create --type residential --country US --zip 94102 -o json
kernel proxies create --type mobile --country US --carrier "T-Mobile" -o json
```

Custom proxy:

```bash
kernel proxies create --type custom --host proxy.example.com --port 8080 -o json
kernel proxies create --type custom --host proxy.example.com --port 8080 --username user --password pass --name "My Proxy" -o json
kernel proxies create --type custom --host proxy.example.com --port 3128 --protocol http -o json
```

Do not print proxy passwords or secrets.

## Inspect And Delete

```bash
kernel proxies list -o json
kernel proxies get <proxy_id_or_name> -o json
kernel proxies delete <proxy_id_or_name> -y
```

## Notes

- `--city` requires `--country`.
- Country values should use ISO 3166 country codes or `EU`.
- Custom proxies require both `--host` and `--port`.
- Protocol defaults to `https` when omitted.
- More specific targeting can reduce available IP capacity.
