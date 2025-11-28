# PhisGuard Backend API

A comprehensive phishing detection backend API built with Flask, providing advanced security analysis for URLs, SSL certificates, link expansions, password breach checking, and email text analysis.

## 🚀 Features

- **URL Security Analysis**: ML-powered phishing detection using Random Forest models
- **SSL Certificate Validation**: Comprehensive SSL/TLS certificate checking
- **Link Expansion Analysis**: Redirect chain analysis and suspicious pattern detection
- **Password Breach Checking**: Local breach database with 2000+ entries
- **Email Text Analysis**: Naive Bayes model for phishing email detection
- **RESTful API**: Clean, documented endpoints with proper authentication
- **Rate Limiting**: Built-in rate limiting with Redis support
- **Comprehensive Logging**: Structured security event logging
- **Docker Support**: Complete containerization for easy deployment

## 📋 Requirements

- Python 3.12+
- pip
- Docker (optional, for containerized deployment)

## 🛠️ Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/phisguard-backend.git
   cd phisguard-backend
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**
   ```bash
   python3 app.py
   ```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t phisguard-backend .
docker run -p 5000:5000 phisguard-backend
```

## ⚙️ Configuration

Create a `.env` file with the following variables:

```env
# Flask Configuration
FLASK_DEBUG=False
SECRET_KEY=your-super-secret-key-here
HOST=0.0.0.0
PORT=5000

# API Security
API_KEY=your-api-key-here

# Admin Access
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password-here

# External API Keys (Optional)
GOOGLE_SAFE_BROWSING_API_KEY=your-google-api-key
VIRUSTOTAL_API_KEY=your-virustotal-api-key
PHISHTANK_API_KEY=your-phishtank-api-key

# Redis (Optional, for production rate limiting)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
LOG_FILE=phisguard.log
```

## 📚 API Documentation

### Base URL
```
http://localhost:5000
```

### Authentication
All API endpoints require an API key in the `X-API-Key` header:
```
X-API-Key: your-api-key-here
```

### Endpoints

#### Health Check
- **GET** `/health` - Basic health check
- **GET** `/api/health` - Detailed API health check

#### Security Analysis
- **POST** `/check-url` - Analyze URL for phishing risks
- **POST** `/check-ssl` - Validate SSL certificate
- **POST** `/expand-link` - Analyze link redirects
- **POST** `/check-breach` - Check password/email breaches
- **POST** `/check-email-text` - Analyze email content for phishing
- **POST** `/comprehensive-check` - Full security analysis

#### User Dashboard
- **GET** `/user/security-dashboard` - Get user security statistics
- **GET** `/user/security-report` - Download security report

#### Feedback
- **POST** `/submit-feedback` - Submit user feedback for model improvement

#### Admin (Basic Auth Required)
- **GET** `/admin/api/analytics` - Security analytics
- **GET** `/admin/api/events` - Recent security events
- **GET** `/admin/api/breaches` - Breach statistics
- **GET** `/admin/api/feedback` - User feedback data
- **GET** `/admin/api/models/status` - ML model status
- **POST** `/admin/api/models/switch` - Switch model versions
- **POST** `/admin/api/models/retrain` - Retrain ML models

### Example API Usage

```python
import requests

# Check URL security
response = requests.post('http://localhost:5000/check-url',
    headers={'X-API-Key': 'your-api-key'},
    json={'url': 'https://example.com'}
)
print(response.json())
```

```bash
# Health check
curl http://localhost:5000/health

# URL analysis
curl -X POST http://localhost:5000/check-url \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d '{"url":"https://example.com"}'
```

## 🧪 Testing

Run the test suite:
```bash
python3 -m pytest tests/ -v
```

Run basic functionality tests:
```bash
python3 test_app.py
```

## 🏗️ Project Structure

```
phisguard-backend/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose setup
├── gunicorn_config.py    # Production server config
├── railway.toml         # Railway deployment config
├── breaches.json        # Local breach database
├── .env.example         # Environment template
├── services/            # Core business logic
│   ├── url_checker.py
│   ├── ssl_checker.py
│   ├── link_expander.py
│   ├── breach_checker.py
│   ├── ml_detector.py
│   └── email_text_detector.py
├── utils/               # Utility modules
│   ├── config.py
│   ├── health.py
│   ├── logger.py
│   ├── cache.py
│   └── risk_scorer.py
├── models/              # ML models and data
├── scripts/             # Training and utility scripts
├── templates/           # Flask templates
└── tests/               # Test suite
```

## 🔒 Security Features

- **API Key Authentication**: Required for all endpoints
- **Rate Limiting**: Configurable request limits with Redis
- **Input Validation**: Comprehensive sanitization and validation
- **CORS Protection**: Configurable cross-origin policies
- **Security Logging**: Structured event logging
- **SSL/TLS Validation**: Certificate verification
- **XSS Protection**: Input sanitization with bleach

## 📊 Machine Learning Models

### URL Phishing Detection
- **Algorithm**: Random Forest Classifier
- **Features**: URL structure, domain analysis, content patterns
- **Training Data**: Balanced dataset with phishing and legitimate URLs

### Email Text Analysis
- **Algorithm**: Naive Bayes with TF-IDF
- **Features**: Text content analysis, keyword detection
- **Training Data**: Phishing and legitimate email samples

## 🚀 Deployment

### Railway (Recommended)
1. Connect your GitHub repository
2. Railway will automatically detect Python app
3. Set environment variables in Railway dashboard
4. Deploy!

### Docker
```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# Development
docker-compose -f docker-compose.dev.yml up
```

### Manual
```bash
# Install gunicorn
pip install gunicorn gevent

# Run with gunicorn
gunicorn --config gunicorn_config.py app:app
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: GitHub Issues
- **Documentation**: This README and inline code comments
- **API Docs**: Available at `/` endpoint when running

## 🔄 Updates

- Regular security updates
- Model retraining with new data
- API enhancements
- Performance optimizations

---

**PhisGuard Backend** - Advanced Phishing Detection API for modern web security.