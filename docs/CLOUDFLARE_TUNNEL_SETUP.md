# Cloudflare Tunnel Setup for ai.isha.buzz

## Summary

Cloudflare Tunnel bypasses port forwarding by creating a secure outbound connection from your server to Cloudflare's network.

## Installation Complete ✅

- **Tunnel ID**: `b6079513-7403-4cc3-8108-a8f8ea3e0281`
- **Tunnel Name**: `ai-isha-buzz`
- **Service**: Installed as systemd service (auto-starts on boot)
- **Status**: Running with 4 active connections

## Configuration

### Tunnel Config (`/etc/cloudflared/config.yml`)
```yaml
tunnel: b6079513-7403-4cc3-8108-a8f8ea3e0281
credentials-file: /etc/cloudflared/b6079513-7403-4cc3-8108-a8f8ea3e0281.json

ingress:
  - hostname: ai.isha.buzz
    service: https://localhost:443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

### Traffic Flow
```
Internet User
    ↓
Cloudflare Edge (Singapore, Mumbai, etc.)
    ↓
Cloudflare Tunnel (encrypted QUIC protocol)
    ↓
Your Server (192.168.1.55:443)
    ↓
Nginx (SSL termination)
    ↓
Backend API (localhost:8000)
```

## DNS Configuration Required

**⚠️ Action Needed in Cloudflare Dashboard:**

1. Go to **DNS** settings for domain `isha.buzz`
2. **Delete** the existing A record:
   - Type: A
   - Name: `ai`
   - Target: `115.99.14.95`

3. **Create** new CNAME record:
   - **Type**: CNAME
   - **Name**: `ai`
   - **Target**: `b6079513-7403-4cc3-8108-a8f8ea3e0281.cfargotunnel.com`
   - **Proxy status**: 🟠 Proxied (orange cloud)
   - **TTL**: Auto

4. Click **Save**

## Service Management

```bash
# Check status
sudo systemctl status cloudflared

# View logs
sudo journalctl -u cloudflared -f

# Restart
sudo systemctl restart cloudflared

# Stop
sudo systemctl stop cloudflared

# Disable auto-start
sudo systemctl disable cloudflared
```

## Verification

After DNS update, test:

```bash
# Test HTTPS
curl -I https://ai.isha.buzz

# Test health endpoint
curl https://ai.isha.buzz/health

# Check DNS resolution
dig ai.isha.buzz CNAME
```

## Troubleshooting

### Tunnel not connecting
```bash
# Check tunnel status
cloudflared tunnel info ai-isha-buzz

# List all tunnels
cloudflared tunnel list

# Test config
cloudflared tunnel run --config /etc/cloudflared/config.yml ai-isha-buzz
```

### Backend not responding (502)
```bash
# Check if backend is running
ss -tlnp | grep :8000

# Start backend
cd /home/dgs/N3090/services/inference-node
nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &

# Check nginx
sudo systemctl status nginx
sudo nginx -t
```

### DNS not updating
- Wait 5-10 minutes for propagation
- Clear browser cache
- Test with: `dig @1.1.1.1 ai.isha.buzz`

## Security Notes

- Tunnel credentials stored in `/etc/cloudflared/`
- Never commit credentials to git
- Origin certificate at `/etc/ssl/origin-certs/ai.isha.buzz.*`
- Cloudflare SSL/TLS mode: **Full (strict)**

## Current Status

| Component | Status | Details |
|-----------|--------|---------|
| Cloudflared Service | ✅ Running | 4 active connections |
| Backend API | ✅ Running | Port 8000 |
| Nginx | ✅ Running | Port 443 (HTTPS) |
| SSL Certificate | ✅ Installed | Cloudflare Origin (ECC) |
| DNS CNAME | ⏳ Pending | Needs manual update |

## Next Steps

1. Update DNS CNAME in Cloudflare (see above)
2. Wait 5 minutes for propagation
3. Test `https://ai.isha.buzz`
4. Verify backend responds to requests

---

**Tunnel Documentation**: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
