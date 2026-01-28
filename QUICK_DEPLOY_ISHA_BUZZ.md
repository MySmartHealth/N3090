# 🚀 Quick Deploy to isha.buzz - Step by Step

## Prerequisites Checklist

- [x] Domain: isha.buzz (already points to 115.99.14.95)
- [x] Public IP: 115.99.14.95
- [x] Internal IP: 192.168.1.55
- [x] SSH access: `ssh dgs@192.168.1.55`
- [ ] Mediqzy API Key (get from Mediqzy)
- [ ] Email address for SSL certificate

---

## ⚡ Fastest Way (2 minutes)

### 1. Update Variables

Get your Mediqzy credentials first, then:

```bash
ssh dgs@192.168.1.55

# Download and run deployment script
cd ~
curl -O https://raw.github.com/MySmartHealth/N3090/main/deploy_isha_buzz.sh

# EDIT BEFORE RUNNING:
nano deploy_isha_buzz.sh

# Find these lines (near top):
EMAIL="your-email@example.com"
MEDIQZY_API_KEY="your-api-key"

# Replace with your actual values, save (Ctrl+X, Y, Enter)
```

### 2. Run Script

```bash
bash deploy_isha_buzz.sh
```

**That's it!** Script will:
- ✅ Install Nginx
- ✅ Install Certbot (SSL)
- ✅ Configure reverse proxy
- ✅ Get SSL certificate
- ✅ Create systemd service
- ✅ Start N3090
- ✅ Test everything

---

## 🔧 Manual Way (5 minutes)

If you prefer to do it step-by-step:

### Step 1: SSH into Server

```bash
ssh dgs@192.168.1.55
```

### Step 2: Install Packages

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### Step 3: Create Nginx Config

```bash
sudo nano /etc/nginx/sites-available/isha.buzz
```

Paste this (replace with your domain):

```nginx
upstream n3090_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name isha.buzz;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name isha.buzz;

    ssl_certificate /etc/letsencrypt/live/isha.buzz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/isha.buzz/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    access_log /var/log/nginx/isha.buzz.access.log;
    error_log /var/log/nginx/isha.buzz.error.log;

    location / {
        proxy_pass http://n3090_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }
}
```

Save: `Ctrl+X`, then `Y`, then `Enter`

### Step 4: Enable Nginx Config

```bash
sudo ln -sf /etc/nginx/sites-available/isha.buzz /etc/nginx/sites-enabled/isha.buzz
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t  # Test config
sudo systemctl reload nginx
```

### Step 5: Get SSL Certificate

```bash
# Replace email with yours!
sudo certbot --nginx -d isha.buzz --non-interactive --agree-tos -m your-email@example.com
```

### Step 6: Create N3090 Service

```bash
# Replace API key with your Mediqzy key!
sudo nano /etc/systemd/system/n3090-inference.service
```

Paste this:

```ini
[Unit]
Description=N3090 Inference Node
After=network.target

[Service]
Type=simple
User=dgs
WorkingDirectory=/home/dgs/N3090/services/inference-node
Environment="PYTHONUNBUFFERED=1"
Environment="EXTERNAL_LLM_ENABLED=true"
Environment="EXTERNAL_LLM_PROVIDER=mediqzy"
Environment="EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com"
Environment="EXTERNAL_LLM_API_KEY=your-api-key-here"
Environment="EXTERNAL_LLM_MODEL=mediqzy-clinical"

ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Save: `Ctrl+X`, `Y`, `Enter`

### Step 7: Enable & Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable n3090-inference
sudo systemctl start n3090-inference

# Check if it's running
sudo systemctl status n3090-inference
```

### Step 8: Test

```bash
# Test locally
curl http://localhost:8000/health

# Test via domain (if SSL cert is ready)
curl https://isha.buzz/health

# Test API
curl -X POST https://isha.buzz/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "test"}],
    "agent_type": "MedicalQA"
  }'
```

---

## 📊 Verify Everything Works

### Check Services Running

```bash
# N3090 service
sudo systemctl status n3090-inference

# Nginx
sudo systemctl status nginx

# Check ports
ss -tlnp | grep -E '(80|443|8000)'
```

### View Logs

```bash
# N3090 logs (real-time)
sudo journalctl -u n3090-inference -f

# Nginx logs
sudo tail -f /var/log/nginx/isha.buzz.error.log
sudo tail -f /var/log/nginx/isha.buzz.access.log
```

### Test Endpoints

```bash
# Health check
curl https://isha.buzz/health

# Chat endpoint
curl https://isha.buzz/v1/chat/completions

# With data
curl -X POST https://isha.buzz/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a healthcare AI"},
      {"role": "user", "content": "What is diabetes?"}
    ],
    "agent_type": "MedicalQA"
  }'
```

---

## 🐛 Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u n3090-inference -n 50

# Check Python path
which python3

# Verify file exists
ls -la /home/dgs/N3090/services/inference-node/app/main.py
```

### Port already in use

```bash
# Find what's using port 8000
sudo lsof -i :8000

# Kill process if needed
sudo kill -9 <PID>
```

### Nginx won't load

```bash
# Check syntax
sudo nginx -t

# Check config file
sudo cat /etc/nginx/sites-available/isha.buzz

# Reload
sudo systemctl reload nginx
```

### SSL Certificate issues

```bash
# Check status
sudo certbot certificates

# Renew if needed
sudo certbot renew

# Auto-renewal status
sudo systemctl list-timers | grep certbot
```

---

## 📋 Configuration Checklist

Before calling production-ready:

- [ ] Nginx installed and running
- [ ] N3090 service running on port 8000
- [ ] SSL certificate obtained (https working)
- [ ] Domain resolves to correct IP
- [ ] API endpoint responds
- [ ] Mediqzy integration configured with real API key
- [ ] Logs being generated correctly
- [ ] Health check working
- [ ] Can test full API call

---

## 🔐 Update Mediqzy API Key (if needed)

```bash
# Edit service file
sudo nano /etc/systemd/system/n3090-inference.service

# Find and update:
Environment="EXTERNAL_LLM_API_KEY=your-real-key"

# Save, then:
sudo systemctl daemon-reload
sudo systemctl restart n3090-inference

# Verify
sudo journalctl -u n3090-inference -n 10
```

---

## 📞 Quick Commands

```bash
# Restart service
sudo systemctl restart n3090-inference

# View logs
sudo journalctl -u n3090-inference -f

# Stop service
sudo systemctl stop n3090-inference

# Reload Nginx
sudo nginx -s reload

# Check SSL cert expiry
sudo certbot certificates

# Test local API
curl http://localhost:8000/v1/chat/completions

# Test via domain
curl https://isha.buzz/v1/chat/completions
```

---

## ✅ Success Indicators

You'll know it's working when:

✅ `https://isha.buzz` responds with HTTPS (green lock)  
✅ `https://isha.buzz/health` returns 200 OK  
✅ API endpoint accepts POST requests  
✅ Logs show successful requests  
✅ `sudo systemctl status n3090-inference` shows "active (running)"  

---

**Ready to deploy!** 🚀

Choose automated (deploy_isha_buzz.sh) or manual steps above.
