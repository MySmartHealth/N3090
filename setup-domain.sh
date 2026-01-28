#!/bin/bash
# Domain Setup Script for isha.buzz
# This script automates the nginx and SSL setup for your domain

set -e

echo "================================"
echo "Domain Setup for isha.buzz"
echo "================================"
echo ""

# Check if running with sudo
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Step 1: Install nginx and certbot if not already installed
echo "Step 1: Installing nginx and certbot..."
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

# Step 2: Copy nginx configuration
echo ""
echo "Step 2: Setting up nginx configuration..."
cp /home/dgs/N3090/docs/nginx-isha-buzz.conf /etc/nginx/sites-available/isha.buzz

# Remove default nginx site if it exists
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
    echo "Removed default nginx site"
fi

# Enable the site
ln -sf /etc/nginx/sites-available/isha.buzz /etc/nginx/sites-enabled/

# Step 3: Create certbot directory
mkdir -p /var/www/certbot

# Step 4: Test nginx configuration
echo ""
echo "Step 3: Testing nginx configuration..."
nginx -t

# Step 5: Start/reload nginx
echo ""
echo "Step 4: Starting nginx..."
systemctl enable nginx
systemctl restart nginx

echo ""
echo "✅ Nginx is running!"
echo ""
echo "================================"
echo "Next Steps:"
echo "================================"
echo ""
echo "1. Make sure your backend is running on port 8000:"
echo "   cd /home/dgs/N3090/services/inference-node"
echo "   pm2 start ecosystem.config.js"
echo ""
echo "2. Test HTTP (should redirect to HTTPS):"
echo "   curl -I http://isha.buzz"
echo ""
echo "3. Get SSL certificate (run this command):"
echo "   sudo certbot certonly --nginx -d isha.buzz -d www.isha.buzz"
echo ""
echo "4. After getting SSL, reload nginx:"
echo "   sudo systemctl reload nginx"
echo ""
echo "5. Test HTTPS:"
echo "   curl -I https://isha.buzz"
echo ""
echo "6. In Cloudflare, set SSL/TLS mode to 'Full (strict)'"
echo "   and enable 'Always Use HTTPS'"
echo ""
echo "================================"
