#!/bin/bash
# Automated deployment script for N3090 on isha.buzz
# Run on rack server: bash deploy_isha_buzz.sh

set -e

echo "╔════════════════════════════════════════════════════════╗"
echo "║  N3090 Deployment on isha.buzz (115.99.14.95)          ║"
echo "╚════════════════════════════════════════════════════════╝"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="isha.buzz"
EMAIL="your-email@example.com"  # Change this!
MEDIQZY_API_KEY="your-api-key"  # Change this!
MEDIQZY_MODEL="mediqzy-clinical"  # Change if different

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# =========================================================
# STEP 1: Update system
# =========================================================
echo ""
echo "STEP 1: Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y
print_status "System updated"

# =========================================================
# STEP 2: Install Nginx
# =========================================================
echo ""
echo "STEP 2: Installing Nginx..."
sudo apt-get install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
print_status "Nginx installed and enabled"

# =========================================================
# STEP 3: Install Certbot
# =========================================================
echo ""
echo "STEP 3: Installing Certbot..."
sudo apt-get install -y certbot python3-certbot-nginx
print_status "Certbot installed"

# =========================================================
# STEP 4: Configure Nginx
# =========================================================
echo ""
echo "STEP 4: Configuring Nginx..."

sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null << EOF
upstream n3090_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;

    # SSL will be configured by certbot
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    access_log /var/log/nginx/$DOMAIN.access.log;
    error_log /var/log/nginx/$DOMAIN.error.log;

    client_max_body_size 100M;

    location / {
        proxy_pass http://n3090_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        
        proxy_buffering off;
    }

    location /health {
        access_log off;
        proxy_pass http://n3090_backend;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
if sudo nginx -t; then
    print_status "Nginx configuration is valid"
else
    print_error "Nginx configuration has errors"
    exit 1
fi

sudo systemctl reload nginx
print_status "Nginx configured and reloaded"

# =========================================================
# STEP 5: Get SSL Certificate
# =========================================================
echo ""
echo "STEP 5: Getting SSL certificate from Let's Encrypt..."

if [ "$EMAIL" == "your-email@example.com" ]; then
    print_warning "Please update EMAIL in script before running!"
    print_warning "Skipping SSL certificate for now"
else
    sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL
    print_status "SSL certificate obtained"
fi

# =========================================================
# STEP 6: Create N3090 Systemd Service
# =========================================================
echo ""
echo "STEP 6: Creating N3090 systemd service..."

if [ "$MEDIQZY_API_KEY" == "your-api-key" ]; then
    print_warning "Please update MEDIQZY_API_KEY in script before running!"
fi

sudo tee /etc/systemd/system/n3090-inference.service > /dev/null << EOF
[Unit]
Description=N3090 Inference Node with Mediqzy Integration
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/N3090/services/inference-node
Environment="PATH=/home/$USER/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="EXTERNAL_LLM_ENABLED=true"
Environment="EXTERNAL_LLM_PROVIDER=mediqzy"
Environment="EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com"
Environment="EXTERNAL_LLM_API_KEY=$MEDIQZY_API_KEY"
Environment="EXTERNAL_LLM_MODEL=$MEDIQZY_MODEL"
Environment="EXTERNAL_LLM_TEMPERATURE=0.7"
Environment="EXTERNAL_LLM_MAX_TOKENS=2048"
Environment="EXTERNAL_LLM_TIMEOUT=30"

ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=n3090

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable n3090-inference
print_status "N3090 systemd service created"

# =========================================================
# STEP 7: Start N3090 Service
# =========================================================
echo ""
echo "STEP 7: Starting N3090 service..."
sudo systemctl start n3090-inference

# Wait for service to start
sleep 3

if sudo systemctl is-active --quiet n3090-inference; then
    print_status "N3090 service started successfully"
else
    print_error "N3090 service failed to start"
    echo "View logs with: sudo journalctl -u n3090-inference -n 50"
    exit 1
fi

# =========================================================
# STEP 8: Verify Setup
# =========================================================
echo ""
echo "STEP 8: Verifying setup..."

# Check if N3090 is listening on port 8000
if sudo ss -tlnp | grep -q "8000"; then
    print_status "N3090 listening on port 8000"
else
    print_error "N3090 not listening on port 8000"
    exit 1
fi

# Check if Nginx is listening on port 443
if sudo ss -tlnp | grep -q "443"; then
    print_status "Nginx listening on port 443"
else
    print_warning "Nginx not listening on port 443 (might be waiting for SSL cert)"
fi

# =========================================================
# STEP 9: Test Endpoints
# =========================================================
echo ""
echo "STEP 9: Testing endpoints..."

# Test health check
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_status "N3090 health check passed"
else
    print_warning "N3090 health check failed (service might still be starting)"
fi

# Test HTTPS if certificate exists
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo ""
    echo "Testing HTTPS endpoint..."
    if curl -s https://$DOMAIN/health > /dev/null 2>&1; then
        print_status "HTTPS endpoint working"
    else
        print_warning "HTTPS endpoint test failed"
    fi
fi

# =========================================================
# Summary
# =========================================================
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  DEPLOYMENT COMPLETE!                                  ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "Configuration Summary:"
echo "  Domain: $DOMAIN"
echo "  Public IP: 115.99.14.95"
echo "  Internal IP: 192.168.1.55"
echo "  SSL: Let's Encrypt"
echo ""

echo "Useful Commands:"
echo "  View logs:        sudo journalctl -u n3090-inference -f"
echo "  Service status:   sudo systemctl status n3090-inference"
echo "  Restart service:  sudo systemctl restart n3090-inference"
echo "  Test API:         curl https://$DOMAIN/health"
echo ""

echo "Next Steps:"
echo "  1. Update EXTERNAL_LLM_API_KEY if needed:"
echo "     sudo nano /etc/systemd/system/n3090-inference.service"
echo "     sudo systemctl daemon-reload && sudo systemctl restart n3090-inference"
echo ""
echo "  2. Monitor logs:"
echo "     sudo journalctl -u n3090-inference -f"
echo ""
echo "  3. Test Mediqzy integration:"
echo "     curl -X POST https://$DOMAIN/v1/chat/completions \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"messages\":[{\"role\":\"user\",\"content\":\"test\"}],\"agent_type\":\"MedicalQA\"}'"
echo ""
echo "DEPLOYMENT STATUS: ✓ SUCCESS"
echo ""
