# Production Deployment on isha.buzz (115.99.14.95)

**Rack Server Setup Guide for N3090 + Mediqzy Integration**

---

## 📋 Current Status

| Component | Status | Details |
|-----------|--------|---------|
| **Internal IP** | ✅ | 192.168.1.55 |
| **Public IP** | ✅ | 115.99.14.95 |
| **Domain** | ✅ | isha.buzz (DNS configured) |
| **Nginx** | ❌ | Not installed |
| **N3090 Service** | ❌ | Not running |
| **HTTPS** | ❌ | Not configured |
| **Llama Server** | ✅ | Running on :8080 (internal) |

---

## 🚀 Deployment Steps

### Step 1: SSH into Server

```bash
ssh dgs@192.168.1.55
# or: ssh -i your-key.pem dgs@192.168.1.55
```

### Step 2: Install Nginx

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Verify installation
nginx -v
certbot --version
```

### Step 3: Configure Nginx as Reverse Proxy

Create Nginx config for isha.buzz:

```bash
sudo tee /etc/nginx/sites-available/isha.buzz > /dev/null << 'EOF'
upstream n3090_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    listen [::]:80;
    server_name isha.buzz;

    # Redirect all HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name isha.buzz;

    # SSL certificates (will be configured by certbot)
    ssl_certificate /etc/letsencrypt/live/isha.buzz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/isha.buzz/privkey.pem;
    
    # SSL best practices
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logging
    access_log /var/log/nginx/isha.buzz.access.log;
    error_log /var/log/nginx/isha.buzz.error.log;

    # Proxy configuration
    location / {
        proxy_pass http://n3090_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering for streaming
        proxy_buffering off;
    }

    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://n3090_backend;
    }
}
EOF
```

Enable the config:

```bash
sudo ln -sf /etc/nginx/sites-available/isha.buzz /etc/nginx/sites-enabled/isha.buzz

# Remove default config if it exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
sudo nginx -t

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx  # Auto-start on reboot
```

### Step 4: Set Up HTTPS with Let's Encrypt

```bash
# Get SSL certificate
sudo certbot --nginx -d isha.buzz --non-interactive --agree-tos -m your-email@example.com

# Verify certificate
sudo certbot certificates
```

### Step 5: Start N3090 Service

Create systemd service file:

```bash
sudo tee /etc/systemd/system/n3090-inference.service > /dev/null << 'EOF'
[Unit]
Description=N3090 Inference Node
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=dgs
WorkingDirectory=/home/dgs/N3090/services/inference-node
Environment="PATH=/home/dgs/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="EXTERNAL_LLM_ENABLED=true"
Environment="EXTERNAL_LLM_PROVIDER=mediqzy"
Environment="EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com"
Environment="EXTERNAL_LLM_API_KEY=your-api-key-here"
Environment="EXTERNAL_LLM_MODEL=mediqzy-clinical"
Environment="EXTERNAL_LLM_TEMPERATURE=0.7"
Environment="EXTERNAL_LLM_MAX_TOKENS=2048"

ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=n3090

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable n3090-inference
sudo systemctl start n3090-inference

# Check status
sudo systemctl status n3090-inference

# View logs
sudo journalctl -u n3090-inference -f
```

### Step 6: Verify HTTPS Setup

```bash
# Test from command line
curl https://isha.buzz/health

# Should return: connection successful

# Test the API
curl -X POST https://isha.buzz/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "test"}],
    "agent_type": "MedicalQA"
  }'
```

---

## 🔐 Configure Mediqzy Integration

Update the systemd service file with your actual Mediqzy credentials:

```bash
sudo nano /etc/systemd/system/n3090-inference.service

# Find and update these lines:
Environment="EXTERNAL_LLM_API_KEY=your-real-api-key"
Environment="EXTERNAL_LLM_MODEL=your-model-name"

# Save (Ctrl+X, Y, Enter)

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart n3090-inference
```

---

## 📊 Monitoring & Logs

### View Nginx Logs

```bash
# Real-time access logs
sudo tail -f /var/log/nginx/isha.buzz.access.log

# Real-time error logs
sudo tail -f /var/log/nginx/isha.buzz.error.log

# Full logs
sudo journalctl -u nginx -f
```

### View N3090 Logs

```bash
# Real-time logs
sudo journalctl -u n3090-inference -f

# Last 100 lines
sudo journalctl -u n3090-inference -n 100

# Errors only
sudo journalctl -u n3090-inference -p err
```

### Check Service Status

```bash
# All services
sudo systemctl status n3090-inference
sudo systemctl status nginx

# Restart if needed
sudo systemctl restart n3090-inference
sudo systemctl restart nginx
```

---

## 🔧 Configuration Options

### Nginx Settings (if needed)

```bash
# Edit nginx config
sudo nano /etc/nginx/sites-available/isha.buzz

# Increase request timeout
proxy_read_timeout 120s;  # For long-running requests

# Change certificate path
sudo certbot renew --force-renewal
```

### N3090 Settings

Edit environment variables in:
```bash
sudo nano /etc/systemd/system/n3090-inference.service
```

Available options:
```bash
EXTERNAL_LLM_TEMPERATURE=0.3        # Lower = more deterministic
EXTERNAL_LLM_MAX_TOKENS=4096        # Longer responses
EXTERNAL_LLM_TIMEOUT=60             # Higher timeout for slow networks
```

---

## 🚨 Troubleshooting

### Port Already in Use

```bash
# Check what's using ports 80/443
sudo lsof -i :80
sudo lsof -i :443

# Kill if needed
sudo kill -9 <PID>
```

### Nginx Not Starting

```bash
# Check config syntax
sudo nginx -t

# View error logs
sudo tail -f /var/log/nginx/error.log

# Restart
sudo systemctl restart nginx
```

### N3090 Not Responding

```bash
# Check if service is running
sudo systemctl status n3090-inference

# Check if port 8000 is listening
sudo ss -tlnp | grep 8000

# Restart service
sudo systemctl restart n3090-inference

# View logs for errors
sudo journalctl -u n3090-inference -n 50
```

### SSL Certificate Issues

```bash
# Check certificate expiry
sudo certbot certificates

# Renew certificate manually
sudo certbot renew --force-renewal

# Auto-renewal (should be running)
sudo systemctl list-timers | grep certbot
```

---

## 📈 Performance Tuning

### Nginx Optimization

```bash
sudo nano /etc/nginx/nginx.conf

# Increase worker processes
worker_processes auto;

# Increase connections
events {
    worker_connections 4096;
}

# Add gzip compression
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```

### Upstream Optimization

If you add more N3090 instances:

```bash
upstream n3090_backend {
    least_conn;  # Load balancing strategy
    server 127.0.0.1:8000;
    # server 127.0.0.1:8001;  # Add more instances
    # server 127.0.0.1:8002;
}
```

---

## 🔐 Security Checklist

- [x] HTTPS enabled (SSL certificate)
- [ ] Update EXTERNAL_LLM_API_KEY with real credentials
- [ ] Restrict SSH access if possible
- [ ] Enable firewall
  ```bash
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw enable
  ```
- [ ] Monitor logs regularly
- [ ] Set up fail2ban (optional)
- [ ] Rotate API keys periodically

---

## 📞 Quick Commands Reference

```bash
# Start/stop services
sudo systemctl start n3090-inference
sudo systemctl stop n3090-inference
sudo systemctl restart n3090-inference

# Check status
sudo systemctl status n3090-inference

# View logs
sudo journalctl -u n3090-inference -f

# Test API
curl https://isha.buzz/v1/chat/completions

# Reload Nginx
sudo nginx -s reload

# Certificate renewal
sudo certbot renew
```

---

## 🎯 What's Next

1. ✅ Run Step 1-6 above
2. ✅ Update Mediqzy API key
3. ✅ Test HTTPS endpoints
4. ✅ Set up monitoring
5. ✅ Document configuration
6. ✅ Schedule certificate renewals

---

**Status**: Ready for Deployment  
**Created**: January 9, 2026  
**Domain**: https://isha.buzz
