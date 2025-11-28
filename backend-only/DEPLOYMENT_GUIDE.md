# PhisGuard Production Deployment Guide

**Version**: 1.0  
**Last Updated**: 2025-11-24  
**Author**: PhisGuard DevOps Team  

---

## 🎯 Overview

This guide provides step-by-step instructions for deploying PhisGuard in a production environment. Follow these instructions carefully to ensure a secure, scalable, and reliable deployment.

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Docker enabled system
- **RAM**: Minimum 2GB (4GB+ recommended)
- **CPU**: 2+ cores (4+ cores recommended)
- **Storage**: 20GB+ available space
- **Network**: Internet connection for external API calls

### Required Software
- **Python**: 3.8+ 
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Git**: Latest version
- **Redis**: 6.0+ (for rate limiting)
- **SSL Certificate**: Valid certificate for HTTPS

### API Keys Required
- **Google Safe Browsing API**: For URL threat detection
- **VirusTotal API**: For comprehensive URL analysis  
- **Have I Been Pwned API**: For breach checking
- **PhishTank API**: For phishing database

---

## 🚀 Quick Start (Docker Deployment)

### Option 1: Docker Compose (Recommended)

1. **Clone and Setup**
   ```bash
   git clone <repository-url> phisguard
   cd phisguard
   ```

2. **Configure Production Environment**
   ```bash
   cp .env.production .env
   # Edit .env with your production values
   nano .env
   ```

3. **Generate Secure Values**
   ```bash
   # Generate secret key
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
   
   # Generate API key
   python3 -c "import secrets; print('API_KEY=' + secrets.token_hex(16))"
   
   # Generate admin password
   python3 -c "import secrets; print('ADMIN_PASSWORD=' + secrets.token_urlsafe(16))"
   ```

4. **Deploy with Docker**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh --prod
   ```

5. **Verify Deployment**
   ```bash
   curl -f http://localhost:5000/health
   ```

---

## 🔧 Detailed Production Setup

### Step 1: System Preparation

#### Install Dependencies (Ubuntu/Debian)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Redis
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Install other dependencies
sudo apt install nginx certbot python3-certbot-nginx -y
```

#### Install Dependencies (CentOS/RHEL)
```bash
# Update system
sudo yum update -y

# Install Python and pip
sudo yum install python3 python3-pip -y

# Install Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y
sudo systemctl enable docker
sudo systemctl start docker

# Install Redis
sudo yum install redis -y
sudo systemctl enable redis
sudo systemctl start redis

# Install Nginx
sudo yum install nginx certbot python3-certbot-nginx -y
```

### Step 2: Application Setup

1. **Clone Repository**
   ```bash
   git clone <repository-url> phisguard
   cd phisguard
   ```

2. **Configure Production Environment**
   ```bash
   # Copy production template
   cp .env.production .env
   
   # Edit configuration
   nano .env
   ```

3. **Required Environment Variables**
   ```env
   # CRITICAL: Generate secure values
   SECRET_KEY=your-secure-secret-key-32-chars
   API_KEY=your-secure-api-key-16-chars
   ADMIN_PASSWORD=your-secure-admin-password
   
   # API Keys (get from respective services)
   GOOGLE_SAFE_BROWSING_API_KEY=your-google-api-key
   VIRUSTOTAL_API_KEY=your-virustotal-api-key
   HIBP_API_KEY=your-hibp-api-key
   PHISHTANK_API_KEY=your-phishtank-api-key
   
   # Redis for rate limiting (production-critical)
   REDIS_URL=redis://localhost:6379/0
   
   # Production settings
   FLASK_DEBUG=False
   HOST=0.0.0.0
   PORT=5000
   LOG_LEVEL=ERROR
   CORS_ORIGINS_STR=https://yourdomain.com
   ```

4. **Generate Secure Configuration**
   ```bash
   # Create secure secrets script
   cat > generate_secrets.sh << 'EOF'
   #!/bin/bash
   echo "Generating secure configuration..."
   
   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")
   ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
   
   sed -i "s/PRODUCTION_SECRET_KEY_GENERATE_SECURE_VALUE_HERE/$SECRET_KEY/" .env
   sed -i "s/PRODUCTION_API_KEY_GENERATE_SECURE_VALUE_HERE/$API_KEY/" .env
   sed -i "s/PRODUCTION_ADMIN_PASSWORD_GENERATE_SECURE_VALUE_HERE/$ADMIN_PASSWORD/" .env
   
   echo "Secure configuration generated!"
   echo "SECRET_KEY: $SECRET_KEY"
   echo "API_KEY: $API_KEY"
   echo "ADMIN_PASSWORD: $ADMIN_PASSWORD"
   EOF
   
   chmod +x generate_secrets.sh
   ./generate_secrets.sh
   ```

### Step 3: SSL/TLS Configuration

1. **Using Let's Encrypt (Recommended)**
   ```bash
   # Install certbot
   sudo apt install certbot python3-certbot-nginx  # Ubuntu
   # sudo yum install certbot python3-certbot-nginx  # CentOS
   
   # Obtain certificate
   sudo certbot --nginx -d yourdomain.com
   
   # Auto-renewal setup
   sudo crontab -e
   # Add: 0 12 * * * /usr/bin/certbot renew --quiet
   ```

2. **Using Custom Certificate**
   ```bash
   # Create SSL directory
   sudo mkdir -p /etc/ssl/phisguard
   
   # Copy your certificate files
   sudo cp your-cert.crt /etc/ssl/phisguard/
   sudo cp your-private.key /etc/ssl/phisguard/
   
   # Set permissions
   sudo chmod 600 /etc/ssl/phisguard/*
   ```

### Step 4: Nginx Reverse Proxy

1. **Create Nginx Configuration**
   ```bash
   sudo nano /etc/nginx/sites-available/phisguard
   ```

2. **Nginx Configuration Content**
   ```nginx
   upstream phisguard_backend {
       server 127.0.0.1:5000;
   }

   server {
       listen 80;
       server_name yourdomain.com www.yourdomain.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name yourdomain.com www.yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
       
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
       ssl_prefer_server_ciphers off;
       ssl_session_cache shared:SSL:10m;

       # Security headers
       add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
       add_header X-Frame-Options DENY;
       add_header X-Content-Type-Options nosniff;
       add_header X-XSS-Protection "1; mode=block";
       add_header Referrer-Policy "strict-origin-when-cross-origin";

       # Rate limiting
       limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
       limit_req zone=api burst=20 nodelay;

       location / {
           proxy_pass http://phisguard_backend;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_connect_timeout 30s;
           proxy_send_timeout 30s;
           proxy_read_timeout 30s;
       }

       location /health {
           proxy_pass http://phisguard_backend;
           access_log off;
       }
   }
   ```

3. **Enable Site**
   ```bash
   sudo ln -s /etc/nginx/sites-available/phisguard /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Step 5: Firewall Configuration

```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 6379/tcp  # Redis (if external)
sudo ufw --force enable

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=6379/tcp  # Redis (if external)
sudo firewall-cmd --reload
```

### Step 6: Monitoring Setup

1. **System Monitoring**
   ```bash
   # Install monitoring tools
   sudo apt install htop iotop nethogs -y
   
   # Set up log rotation
   sudo nano /etc/logrotate.d/phisguard
   ```

2. **Logrotate Configuration**
   ```bash
   /var/log/phisguard/*.log {
       daily
       missingok
       rotate 52
       compress
       delaycompress
       notifempty
       create 644 www-data www-data
       postrotate
           systemctl reload phisguard
       endscript
   }
   ```

---

## 🔧 Deployment Methods

### Method 1: Docker Deployment (Recommended)

1. **Deploy with Docker Compose**
   ```bash
   # Build and start
   docker-compose up -d
   
   # Check status
   docker-compose ps
   
   # View logs
   docker-compose logs -f
   ```

2. **Update Application**
   ```bash
   # Pull latest changes
   git pull origin main
   
   # Rebuild and restart
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Method 2: Direct Python Deployment

1. **Setup Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn gevent
   ```

2. **Start with Gunicorn**
   ```bash
   # Start application
   gunicorn --config gunicorn_config.py app:app
   
   # Or with systemd service
   sudo cp phisguard.service /etc/systemd/system/
   sudo systemctl enable phisguard
   sudo systemctl start phisguard
   ```

3. **Systemd Service File**
   ```ini
   [Unit]
   Description=PhisGuard Backend Service
   After=network.target redis.service

   [Service]
   Type=notify
   User=phisguard
   Group=phisguard
   WorkingDirectory=/opt/phisguard
   Environment=PATH=/opt/phisguard/venv/bin
   ExecStart=/opt/phisguard/venv/bin/gunicorn --config gunicorn_config.py app:app
   ExecReload=/bin/kill -s HUP $MAINPID
   KillMode=mixed
   TimeoutStopSec=5
   PrivateTmp=true
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

---

## 🔍 Health Checks and Monitoring

### Application Health Check
```bash
# Basic health check
curl -f http://localhost:5000/health

# Detailed health check
curl -f http://localhost:5000/health/detailed

# Extension health check
curl -f http://localhost:5000/extension/health
```

### System Monitoring
```bash
# Check application status
docker-compose ps

# View real-time logs
tail -f logs/phisguard.log

# Monitor system resources
htop
iotop
```

### Log Monitoring
```bash
# Application logs
tail -f logs/phisguard.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# System logs
journalctl -u phisguard -f
```

---

## 🚨 Troubleshooting

### Common Issues

#### 1. Application Won't Start
```bash
# Check logs
docker-compose logs phisguard-backend
# Or: tail -f logs/phisguard.log

# Check environment variables
docker-compose exec phisguard-backend env | grep -E "(SECRET_KEY|API_KEY)"

# Verify configuration
python3 -c "from utils.config import get_settings; print(get_settings())"
```

#### 2. Rate Limiting Issues
```bash
# Check Redis connection
redis-cli ping

# Verify Redis URL configuration
echo $REDIS_URL

# Test rate limiting
curl -I http://localhost:5000/check-url
```

#### 3. SSL/TLS Issues
```bash
# Check certificate validity
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Renew Let's Encrypt certificate
sudo certbot renew

# Check Nginx configuration
sudo nginx -t
```

#### 4. API Key Issues
```bash
# Test Google Safe Browsing API
curl "https://safebrowsing.googleapis.com/v4/threatMatches:find?key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"client": {"clientId": "phisguard", "clientVersion": "1.0"}, "threatInfo": {"threatTypes": ["MALWARE"], "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"], "threatEntries": [{"url": "http://malware.testing.google.test/testing/malware/"}]}}'

# Test VirusTotal API
curl "https://www.virustotal.com/vtapi/v2/url/report?apikey=YOUR_API_KEY&resource=example.com"
```

### Performance Issues

#### 1. High Memory Usage
```bash
# Check memory usage
free -h
docker stats

# Optimize Gunicorn workers
# Reduce workers in gunicorn_config.py
workers = 2  # Adjust based on available memory
```

#### 2. Slow Response Times
```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:5000/health"

# Create curl format file
cat > curl-format.txt << EOF
     time_namelookup:  %{time_namelookup}\\n
        time_connect:  %{time_connect}\\n
     time_appconnect:  %{time_appconnect}\\n
    time_pretransfer:  %{time_pretransfer}\\n
       time_redirect:  %{time_redirect}\\n
  time_starttransfer:  %{time_starttransfer}\\n
                     ----------\\n
          time_total:  %{time_total}\\n
EOF
```

### Security Issues

#### 1. API Key Leaks
```bash
# Check for exposed API keys in logs
grep -r "api_key\|API_KEY" logs/ | grep -v "REDACTED"

# Rotate API keys if compromised
# Update .env file with new keys
# Restart application
```

#### 2. Failed Authentication Attempts
```bash
# Check security logs
tail -f logs/phisguard.log | grep "INVALID_API_KEY\|INVALID_ADMIN_AUTH"

# Monitor failed attempts
grep "Invalid or missing API key" logs/phisguard.log | wc -l
```

---

## 📈 Scaling and Optimization

### Horizontal Scaling

1. **Load Balancer Setup**
   ```nginx
   upstream phisguard_backend {
       server 127.0.0.1:5000;
       server 127.0.0.1:5001;
       server 127.0.0.1:5002;
   }
   ```

2. **Redis Cluster for Rate Limiting**
   ```bash
   # Install Redis Cluster
   # Configure multiple Redis instances
   # Update REDIS_URL to cluster connection string
   ```

### Performance Optimization

1. **Application Level**
   - Enable caching for ML model results
   - Optimize database queries
   - Use connection pooling
   - Implement async processing

2. **System Level**
   - Tune kernel parameters
   - Optimize file system
   - Use SSD storage
   - Enable HTTP/2

### Monitoring and Alerting

1. **Set up monitoring with Prometheus/Grafana**
2. **Configure log aggregation with ELK stack**
3. **Set up alerts for critical issues**
4. **Monitor business metrics**

---

## 🔐 Security Checklist

### Pre-Deployment Security Audit
- [ ] All API keys are secure and not hardcoded
- [ ] SECRET_KEY is cryptographically secure (32+ chars)
- [ ] ADMIN_PASSWORD is strong and secure
- [ ] CORS origins are restricted to production domains
- [ ] Rate limiting is configured with Redis
- [ ] SSL/TLS is properly configured
- [ ] Firewall rules are restrictive
- [ ] Logs are secured and rotated
- [ ] System updates are applied
- [ ] Security headers are implemented

### Ongoing Security Maintenance
- [ ] Regular security updates
- [ ] API key rotation
- [ ] Security log monitoring
- [ ] Penetration testing
- [ ] Vulnerability scanning
- [ ] Certificate renewal
- [ ] Backup verification

---

## 📞 Support and Maintenance

### Regular Maintenance Tasks

1. **Daily**
   - Check application health
   - Monitor error logs
   - Review security events

2. **Weekly**
   - Update system packages
   - Review performance metrics
   - Check backup integrity

3. **Monthly**
   - Security audit
   - API key rotation
   - Performance optimization
   - Disaster recovery testing

### Emergency Procedures

1. **Application Down**
   ```bash
   # Quick restart
   docker-compose restart
   
   # Full recovery
   docker-compose down
   docker-compose up -d
   ```

2. **Security Incident**
   ```bash
   # Revoke compromised API keys
   # Update configuration
   # Restart services
   # Review logs
   ```

3. **Data Recovery**
   ```bash
   # Restore from backup
   # Verify data integrity
   # Update configurations
   ```

---

## 📚 Additional Resources

### Documentation
- [Flask Production Deployment](https://flask.palletsprojects.com/en/2.0.x/deploying/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Redis Documentation](https://redis.io/documentation)

### Support Channels
- **GitHub Issues**: For bug reports and feature requests
- **Security**: security@phisguard.com
- **Community**: Discord server (link in README)

### Training Resources
- **Docker Training**: Docker's official training materials
- **Flask Deployment**: Comprehensive Flask deployment guide
- **Security Best Practices**: OWASP guidelines

---

*This deployment guide is maintained by the PhisGuard DevOps team. For updates and improvements, please contribute via GitHub.*