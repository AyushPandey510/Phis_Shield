import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
try:
    from flask_limiter.extension import RedisStorage
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from services.url_checker import check_url
from services.ssl_checker import check_ssl
from services.link_expander import expand_link
from services.breach_checker import check_password_breach, check_password_strength, comprehensive_security_check, load_breach_data
from services.email_text_detector import email_detector
from utils.risk_scorer import RiskScorer, quick_risk_assessment
from utils.logger import get_security_logger
from utils.config import get_settings
from utils.health import get_health_checker
from utils.cache import get_cache
import os
import logging
import bleach
import validators
import traceback
import time
import json
from datetime import datetime
from email_validator import validate_email as validate_email_lib, EmailNotValidError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get application settings
settings = get_settings()

app = Flask(__name__)

# Initialize security logger
security_logger = get_security_logger()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize rate limiter with Redis support for production
def create_limiter(app):
    """Create rate limiter with appropriate storage backend"""
    storage_url = settings.redis_url
    
    if REDIS_AVAILABLE and storage_url:
        try:
            # Use Redis for production
            storage = RedisStorage.from_url(storage_url)
            logger.info(f"Rate limiter using Redis storage: {storage_url}")
            limiter = Limiter(
                storage=storage,
                default_limits=["200 per day", "50 per hour"]
            )
            limiter.init_app(app)
            return limiter
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for rate limiting: {str(e)}. Using in-memory storage.")
    
    # Fallback to in-memory storage for development
    if not storage_url:
        logger.warning("No Redis URL configured. Using in-memory storage for rate limiting (not recommended for production).")
    
    limiter = Limiter(
        get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    limiter.init_app(app)
    return limiter

limiter = create_limiter(app)

# Disable Flask-Talisman for extension compatibility
# Add basic security headers manually
@app.after_request
def add_security_headers(response):
    """Add basic security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Configure CORS for API access
CORS(app, origins=["*"], supports_credentials=True, methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-API-Key"])

# Configuration from settings
app.config['DEBUG'] = settings.debug
app.config['SECRET_KEY'] = settings.secret_key
app.config['MAX_CONTENT_LENGTH'] = settings.max_content_length
app.config['PERMANENT_SESSION_LIFETIME'] = settings.permanent_session_lifetime
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for security
app.config['API_KEY'] = settings.api_key
app.config['TIMEOUT'] = settings.request_timeout

# Force load breach data on startup
try:
    logger.info("Loading breach data on application startup...")
    load_breach_data()
    logger.info("Breach data loaded successfully")
except Exception as e:
    logger.error(f"Failed to load breach data on startup: {str(e)}")


# Security validation functions
def sanitize_input(text):
    """Sanitize input to prevent XSS and injection attacks"""
    if not isinstance(text, str):
        return ""
    return bleach.clean(text, tags=[], attributes={}, strip=True)

def validate_url(url):
    """Validate and normalize URL"""
    if not url or not isinstance(url, str):
        return None, "Invalid URL format"

    url = sanitize_input(url.strip())
    if not url:
        return None, "URL is required"

    # Strip fragment (#) before validation as validators library doesn't allow fragments
    url_no_fragment = url.split('#')[0]

    # Use validators library for URL validation
    try:
        if not validators.url(url_no_fragment):
            return None, "Invalid URL format"
    except Exception:
        return None, "Invalid URL format"

    # Normalize URL (keep original with fragment)
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    return url, None

def validate_email(email):
    """Validate email format"""
    if not email or not isinstance(email, str):
        return None, "Invalid email format"

    email = sanitize_input(email.strip())
    if not email:
        return None, "Email is required"

    # Allow @example.com emails for testing purposes
    if email.endswith('@example.com'):
        # Basic email format validation for @example.com
        import re
        if re.match(r'^[a-zA-Z0-9._%+-]+@example\.com$', email):
            return email, None
        else:
            return None, "Invalid email format"

    try:
        valid = validate_email_lib(email)
        return valid.email, None
    except EmailNotValidError as e:
        return None, str(e)

def validate_password_strength(password):
    """Validate password meets minimum requirements"""
    if not password or not isinstance(password, str):
        return False, "Password is required"

    password = sanitize_input(password)
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit"
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(char.islower() for char in password):
        return False, "Password must contain at least one lowercase letter"

    return True, None

def log_security_event(event_type, details, ip_address, user_agent=None, endpoint=None, level='WARNING', user_id=None):
    """Log security-related events in structured format"""
    security_logger.log_security_event(
        event_type=event_type,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent or request.headers.get('User-Agent', 'Unknown'),
        endpoint=endpoint or request.path,
        level=level,
        user_id=user_id
    )

def require_api_key(f):
    """Decorator to require API key for endpoints"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key or api_key != app.config['API_KEY']:
            log_security_event("INVALID_API_KEY", "Missing or invalid API key", request.remote_addr, request.headers.get('User-Agent'), request.path)
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_basic_auth(f):
    """Decorator to require basic authentication for admin endpoints"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == settings.admin_username and auth.password == settings.admin_password):
            log_security_event("INVALID_ADMIN_AUTH", "Missing or invalid admin credentials", request.remote_addr, request.headers.get('User-Agent'), request.path)
            return jsonify({"error": "Invalid admin credentials"}), 401
        return f(*args, **kwargs)
    return decorated_function

def parse_analytics_from_logs():
    """Parse analytics data from log files"""
    log_file = settings.log_file
    if not os.path.exists(log_file):
        return {
            "total_checks": 0,
            "safe_count": 0,
            "caution_count": 0,
            "danger_count": 0,
            "top_urls": []
        }

    total_checks = 0
    safe_count = 0
    caution_count = 0
    danger_count = 0
    url_counts = {}

    try:
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    if log_entry.get('event_type') == 'api_request':
                        total_checks += 1
                        endpoint = log_entry.get('endpoint', '')
                        if 'check-url' in endpoint:
                            # For URL checks, we don't have risk scores in logs
                            # This is a limitation; in production, we'd log more details
                            pass
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Error parsing log file: {str(e)}")

    # For demo purposes, return mock data
    return {
        "total_checks": total_checks,
        "safe_count": max(1, total_checks // 3),
        "caution_count": max(1, total_checks // 3),
        "danger_count": max(1, total_checks // 3),
        "top_urls": [
            {"url": "example.com", "risk_score": 85, "checks": 5},
            {"url": "suspicious-site.net", "risk_score": 92, "checks": 3},
            {"url": "phishing-test.org", "risk_score": 78, "checks": 2}
        ]
    }

def get_recent_events():
    """Get recent security events from logs"""
    log_file = settings.log_file
    events = []

    if not os.path.exists(log_file):
        return events

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()[-50:]  # Last 50 lines
            for line in reversed(lines):
                try:
                    log_entry = json.loads(line.strip())
                    if log_entry.get('event_type') not in ['api_request']:
                        events.append(log_entry)
                    if len(events) >= 20:  # Limit to 20 events
                        break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")

    return events

def get_breach_statistics():
    """Get breach statistics"""
    import json
    try:
        with open('breaches.json', 'r') as f:
            breaches = json.load(f)
            total_breaches = len(breaches)
            # Mock breached vs safe
            return {
                "total_breaches": total_breaches,
                "breached_count": total_breaches,
                "safe_count": 1000  # Mock safe count
            }
    except Exception as e:
        logger.error(f"Error reading breaches file: {str(e)}")
        return {
            "total_breaches": 0,
            "breached_count": 0,
            "safe_count": 0
        }

def get_user_reports():
    """Get user reports (placeholder)"""
    # Placeholder for user reports - in real implementation, this would come from a database
    return {
        "pending_count": 0,
        "reports": []
    }

def get_user_security_data(user_id, include_detailed=False):
    """Get security dashboard data for a specific user"""
    log_file = settings.log_file
    feedback_file = 'data/user_feedback.jsonl'

    # Initialize counters
    protected_count = 0
    high_risk_count = 0
    medium_risk_count = 0
    low_risk_count = 0
    weekly_checks = 0
    recent_detections = []
    security_timeline = []
    threat_categories = {}

    # Current time for filtering
    now = datetime.now()
    week_ago = now.replace(day=now.day - 7) if now.day > 7 else now.replace(month=now.month - 1, day=28)

    try:
        # Parse security logs
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())

                        # Check if this log entry is from the user (by user_id or IP)
                        user_matches = (
                            log_entry.get('user_id') == user_id or
                            log_entry.get('ip_address') == user_id or
                            not user_id
                        )

                        if user_matches:
                            event_type = log_entry.get('event_type', '')

                            # Count URL checks
                            if event_type == 'api_request' and 'check-url' in log_entry.get('endpoint', ''):
                                protected_count += 1

                                # Check timestamp for weekly count
                                timestamp_str = log_entry.get('timestamp', '')
                                if timestamp_str:
                                    try:
                                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                        if timestamp > week_ago:
                                            weekly_checks += 1
                                    except:
                                        pass

                            # Add to timeline
                            if event_type in ['api_request', 'security_event']:
                                security_timeline.append({
                                    'timestamp': log_entry.get('timestamp', ''),
                                    'event': f"{event_type}: {log_entry.get('endpoint', 'Unknown')}"
                                })

                    except json.JSONDecodeError:
                        continue

        # Parse feedback data for risk analysis
        if os.path.exists(feedback_file):
            with open(feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        feedback_item = json.loads(line.strip())

                        # Check if feedback is from this user (multiple identifier fields)
                        user_matches = (
                            feedback_item.get('user_id') == user_id or
                            feedback_item.get('extension_user_id') == user_id or
                            feedback_item.get('ip_address') == user_id or
                            not user_id
                        )

                        if user_matches:
                            risk_score = feedback_item.get('original_risk_score', 0)

                            # Categorize by risk level
                            if risk_score >= 70:
                                high_risk_count += 1
                            elif risk_score >= 40:
                                medium_risk_count += 1
                            else:
                                low_risk_count += 1

                            # Add to recent detections if recent
                            timestamp_str = feedback_item.get('timestamp', '')
                            if timestamp_str:
                                try:
                                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    if timestamp > week_ago:
                                        recent_detections.append({
                                            'timestamp': timestamp_str,
                                            'url': feedback_item.get('url', 'Unknown'),
                                            'risk_level': 'danger' if risk_score >= 70 else 'caution' if risk_score >= 40 else 'safe'
                                        })
                                except:
                                    pass

                            # Count threat categories
                            correction = feedback_item.get('user_correction', '')
                            if correction:
                                threat_categories[correction] = threat_categories.get(correction, 0) + 1

                    except json.JSONDecodeError:
                        continue

        # Sort and limit results
        recent_detections.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        recent_detections = recent_detections[:10]  # Last 10 detections

        security_timeline.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        security_timeline = security_timeline[:20]  # Last 20 events

        return {
            "protected_count": protected_count,
            "high_risk_count": high_risk_count,
            "medium_risk_count": medium_risk_count,
            "low_risk_count": low_risk_count,
            "weekly_checks": weekly_checks,
            "recent_detections": recent_detections,
            "security_timeline": security_timeline,
            "threat_categories": threat_categories,
            "generated_at": now.isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting user security data: {str(e)}")
        return {
            "protected_count": 0,
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "weekly_checks": 0,
            "recent_detections": [],
            "security_timeline": [],
            "threat_categories": {},
            "error": "Failed to load security data"
        }

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "PhisGuard Backend API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "check_url": "/check-url",
            "check_ssl": "/check-ssl",
            "expand_link": "/expand-link",
            "check_breach": "/check-breach",
            "check_email_text": "/check-email-text",
            "comprehensive_check": "/comprehensive-check"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({"status": "healthy", "service": "phisguard-backend"})

@app.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with system and application metrics"""
    health_checker = get_health_checker()
    return jsonify(health_checker.get_full_health_report())

@app.route('/api/health', methods=['GET'])
def api_health_check():
    return jsonify({
        "status": "healthy",
        "service": "phisguard-backend",
        "api_version": "1.0.0",
        "cors_enabled": True
    })

@app.route('/check-url', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def check_url_endpoint():
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing request data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    url = data.get('url')
    if not url:
        log_security_event("MISSING_URL", "URL parameter missing", request.remote_addr)
        return jsonify({"error": "URL is required"}), 400

    # Extract user ID for tracking
    user_id = data.get('user_id') or request.remote_addr

    # Validate and sanitize URL
    validated_url, error = validate_url(url)
    if error:
        log_security_event("INVALID_URL", f"URL validation failed: {error}", request.remote_addr, user_agent=request.headers.get('User-Agent'), endpoint=request.path, user_id=user_id)
        return jsonify({"error": error}), 400

    try:
        risk_score, details = check_url(validated_url)

        # Log successful URL check with user ID
        log_security_event("URL_CHECK", f"URL: {validated_url}, Risk: {risk_score}", request.remote_addr, request.headers.get('User-Agent'), request.path, level='INFO', user_id=user_id)


        return jsonify({
            "url": validated_url,
            "risk_score": risk_score,
            "details": details,
            "recommendation": "safe" if risk_score < 30 else "caution" if risk_score < 70 else "danger"
        })
    except Exception as e:
        logger.error(f"Error in check_url_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/check-ssl', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def check_ssl_endpoint():
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing request data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    url = data.get('url')
    if not url:
        log_security_event("MISSING_URL", "URL parameter missing", request.remote_addr)
        return jsonify({"error": "URL is required"}), 400

    # Validate and sanitize URL
    validated_url, error = validate_url(url)
    if error:
        log_security_event("INVALID_URL", f"URL validation failed: {error}", request.remote_addr)
        return jsonify({"error": error}), 400

    try:
        is_valid, details = check_ssl(validated_url)
        return jsonify({
            "url": validated_url,
            "ssl_valid": is_valid,
            "details": details
        })
    except Exception as e:
        logger.error(f"Error in check_ssl_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/expand-link', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def expand_link_endpoint():
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing request data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    url = data.get('url')
    if not url:
        log_security_event("MISSING_URL", "URL parameter missing", request.remote_addr)
        return jsonify({"error": "URL is required"}), 400

    # Validate and sanitize URL
    validated_url, error = validate_url(url)
    if error:
        log_security_event("INVALID_URL", f"URL validation failed: {error}", request.remote_addr)
        return jsonify({"error": error}), 400

    try:
        final_url, redirect_chain, analysis, error = expand_link(validated_url)
        if error:
            # Provide user-friendly error messages
            if "Connection refused" in error or "Failed to establish a new connection" in error:
                user_friendly_error = "Unable to connect to the URL. The website may be down or not responding."
            elif "timeout" in error.lower():
                user_friendly_error = "Request timed out. The website is taking too long to respond."
            elif "Invalid URL" in error:
                user_friendly_error = "The URL format is invalid."
            else:
                user_friendly_error = "Unable to expand the link. Please check if the URL is accessible."

            return jsonify({
                "error": user_friendly_error,
                "technical_details": error if app.config['DEBUG'] else None,
                "url": validated_url
            }), 400

        return jsonify({
            "original_url": validated_url,
            "final_url": final_url,
            "redirect_chain": redirect_chain,
            "redirect_count": len(redirect_chain),
            "analysis": analysis
        })
    except Exception as e:
        logger.error(f"Error in expand_link_endpoint: {str(e)}")
        return jsonify({
            "error": "An unexpected error occurred while expanding the link.",
            "url": validated_url
        }), 500

@app.route('/check-breach', methods=['POST'])
@limiter.limit("5 per minute")  # Stricter limit for breach checks
@require_api_key
def check_breach_endpoint():
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing request data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    email = data.get('email')
    password = data.get('password')

    if not email and not password:
        log_security_event("MISSING_CREDENTIALS", "Neither email nor password provided", request.remote_addr)
        return jsonify({"error": "Either email or password must be provided"}), 400

    # Validate email if provided
    if email:
        validated_email, error = validate_email(email)
        if error:
            log_security_event("INVALID_EMAIL", f"Email validation failed: {error}", request.remote_addr)
            return jsonify({"error": error}), 400
        email = validated_email

    # For breach checking, we only validate basic requirements (not full strength)
    # This allows checking if weak passwords have been breached
    if password:
        password = sanitize_input(password)
        if len(password) < 1:
            return jsonify({"error": "Password cannot be empty"}), 400
        # Skip full strength validation for breach checks - we want to check ALL passwords

    try:
        if password and not email:
            # Password-only check
            breached, count = check_password_breach(password)
            strength_score, feedback = check_password_strength(password)
            return jsonify({
                "password_check": {
                    "breached": breached,
                    "breach_count": count
                },
                "password_strength": {
                    "score": strength_score,
                    "feedback": feedback
                }
            })
        else:
            # Comprehensive check
            results = comprehensive_security_check(email, password)
            return jsonify(results)
    except Exception as e:
        logger.error(f"Error in check_breach_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/check-email-text', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def check_email_text_endpoint():
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing request data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    subject = data.get('subject', '')
    body = data.get('body', '')

    if not subject and not body:
        log_security_event("MISSING_EMAIL_CONTENT", "Neither subject nor body provided", request.remote_addr)
        return jsonify({"error": "Either subject or body must be provided"}), 400

    # Sanitize inputs
    subject = sanitize_input(subject)
    body = sanitize_input(body)

    try:
        risk_score, analysis = email_detector.predict(subject, body)

        return jsonify({
            "subject": subject[:100] + "..." if len(subject) > 100 else subject,  # Truncate for response
            "body_preview": body[:200] + "..." if len(body) > 200 else body,
            "risk_score": risk_score,
            "analysis": analysis,
            "recommendation": "safe" if risk_score < 0.3 else "caution" if risk_score < 0.7 else "danger"
        })
    except Exception as e:
        logger.error(f"Error in check_email_text_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/submit-feedback', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def submit_feedback_endpoint():
    """Submit user feedback for model improvement."""
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing feedback data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    url = data.get('url')
    if not url:
        log_security_event("MISSING_URL", "URL missing from feedback", request.remote_addr)
        return jsonify({"error": "URL is required"}), 400

    # Validate URL
    validated_url, error = validate_url(url)
    if error:
        log_security_event("INVALID_URL", f"Invalid URL in feedback: {error}", request.remote_addr)
        return jsonify({"error": error}), 400

    try:
        # Prepare feedback data
        feedback_data = {
            'url': validated_url,
            'original_risk_score': data.get('risk_score'),
            'original_recommendation': data.get('recommendation'),
            'is_correct': data.get('is_correct'),
            'user_correction': data.get('user_correction') or data.get('corrected_label'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'ip_address': request.remote_addr,
            'source': 'extension_feedback'
        }

        # Save feedback to file (in production, this would go to a database)
        feedback_file = 'data/user_feedback.jsonl'
        os.makedirs(os.path.dirname(feedback_file), exist_ok=True)

        with open(feedback_file, 'a', encoding='utf-8') as f:
            json.dump(feedback_data, f, ensure_ascii=False)
            f.write('\n')

        logger.info(f"Feedback saved for URL: {validated_url}")

        return jsonify({
            "message": "Feedback submitted successfully",
            "feedback_id": len(open(feedback_file).readlines()) if os.path.exists(feedback_file) else 1
        })

    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/user/security-dashboard', methods=['GET'])
def user_security_dashboard():
    """Get user's security dashboard data"""
    try:
        # Get user identifier from query parameter or fallback to IP
        user_id = request.args.get('user_id') or request.remote_addr

        # Parse security events from logs for this user
        dashboard_data = get_user_security_data(user_id)

        return jsonify(dashboard_data)
    except Exception as e:
        logger.error(f"Error in user_security_dashboard: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/user/security-report', methods=['GET'])
def user_security_report():
    """Get user's security report data for download"""
    try:
        # Get user identifier from query parameter or fallback to IP
        user_id = request.args.get('user_id') or request.remote_addr

        # Get comprehensive security data
        report_data = get_user_security_data(user_id, include_detailed=True)

        return jsonify(report_data)
    except Exception as e:
        logger.error(f"Error in user_security_report: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/comprehensive-check', methods=['POST'])
@limiter.limit("5 per minute")  # Stricter limit for comprehensive checks
@require_api_key
def comprehensive_check_endpoint():
    data = request.get_json()
    if not data:
        log_security_event("INVALID_REQUEST", "Missing request data", request.remote_addr)
        return jsonify({"error": "Request data is required"}), 400

    url = data.get('url')
    if not url:
        log_security_event("MISSING_URL", "URL parameter missing", request.remote_addr)
        return jsonify({"error": "URL is required"}), 400

    email = data.get('email')
    password = data.get('password')
    email_subject = data.get('email_subject')
    email_body = data.get('email_body')

    # Validate URL
    validated_url, error = validate_url(url)
    if error:
        log_security_event("INVALID_URL", f"URL validation failed: {error}", request.remote_addr)
        return jsonify({"error": error}), 400

    # Validate email if provided
    if email:
        validated_email, error = validate_email(email)
        if error:
            log_security_event("INVALID_EMAIL", f"Email validation failed: {error}", request.remote_addr)
            return jsonify({"error": error}), 400
        email = validated_email

    # Validate password strength if provided
    if password:
        valid, error = validate_password_strength(password)
        if not valid:
            log_security_event("WEAK_PASSWORD", f"Password validation failed: {error}", request.remote_addr)
            return jsonify({"error": error}), 400

    try:
        scorer = RiskScorer()

        # Gather results from all checkers
        url_results = None
        ssl_results = None
        link_results = None
        breach_results = None
        email_text_results = None

        # URL check
        url_risk, url_details = check_url(validated_url)
        url_results = {
            "risk_score": url_risk,
            "details": url_details,
            "recommendation": "safe" if url_risk < 30 else "caution" if url_risk < 70 else "danger"
        }

        # SSL check
        try:
            ssl_valid, ssl_details = check_ssl(validated_url)
            ssl_results = {"is_valid": ssl_valid, **ssl_details}
        except Exception as e:
            logger.error(f"SSL check failed for {validated_url}: {str(e)}")
            ssl_results = {
                "error": "SSL check failed - rate limit or service unavailable",
                "risk_score": 0,
                "risk_flags": ["⚠️ SSL analysis temporarily unavailable"],
                "connection_type": "unknown"
            }

        # Link expansion check
        try:
            final_url, redirect_chain, link_analysis, link_error = expand_link(validated_url)
            link_results = {
                "final_url": final_url,
                "redirect_chain": redirect_chain,
                "analysis": link_analysis,
                "error": link_error
            }
        except Exception as e:
            logger.error(f"Link expansion failed for {validated_url}: {str(e)}")
            link_results = {
                "error": "Link expansion failed - rate limit or service unavailable",
                "final_url": validated_url,
                "redirect_chain": [],
                "analysis": {
                    "risk_flags": ["⚠️ Link analysis temporarily unavailable"],
                    "risk_score": 0,
                    "suspicious": False
                }
            }

        # Breach check (if credentials provided)
        if email or password:
            breach_results = comprehensive_security_check(email, password)

        # Email text check (if email content provided)
        if email_subject or email_body:
            email_subject = sanitize_input(email_subject or '')
            email_body = sanitize_input(email_body or '')
            email_risk, email_analysis = email_detector.predict(email_subject, email_body)
            email_text_results = {
                "risk_score": email_risk,
                "analysis": email_analysis,
                "recommendation": "safe" if email_risk < 0.3 else "caution" if email_risk < 0.7 else "danger"
            }

        # Calculate overall risk
        assessment = scorer.calculate_overall_risk(
            url_results=url_results,
            ssl_results=ssl_results,
            link_results=link_results,
            breach_results=breach_results,
            email_text_results=email_text_results
        )

        return jsonify({
            "url": validated_url,
            "assessment": assessment,
            "individual_checks": {
                "url_check": url_results,
                "ssl_check": ssl_results,
                "link_expansion": link_results,
                "breach_check": breach_results,
                "email_text_check": email_text_results
            }
        })

    except Exception as e:
        logger.error(f"Error in comprehensive_check_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# Admin Dashboard Routes
@app.route('/admin/', methods=['GET'])
def admin_dashboard():
    """Admin dashboard page (no auth required for demo)"""
    return render_template('dashboard.html')

@app.route('/admin/api/analytics', methods=['GET'])
@require_basic_auth
def admin_analytics():
    """Get analytics data"""
    try:
        # Parse log file for analytics
        analytics = parse_analytics_from_logs()
        return jsonify(analytics)
    except Exception as e:
        logger.error(f"Error in admin_analytics: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/events', methods=['GET'])
@require_basic_auth
def admin_events():
    """Get recent security events"""
    try:
        events = get_recent_events()
        return jsonify({"events": events})
    except Exception as e:
        logger.error(f"Error in admin_events: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/breaches', methods=['GET'])
@require_basic_auth
def admin_breaches():
    """Get breach statistics"""
    try:
        breaches = get_breach_statistics()
        return jsonify(breaches)
    except Exception as e:
        logger.error(f"Error in admin_breaches: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/reports', methods=['GET'])
@require_basic_auth
def admin_reports():
    """Get user reports"""
    try:
        reports = get_user_reports()
        return jsonify(reports)
    except Exception as e:
        logger.error(f"Error in admin_reports: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/feedback', methods=['GET'])
@require_basic_auth
def admin_feedback():
    """Get user feedback data"""
    try:
        feedback_file = 'data/user_feedback.jsonl'
        feedback_data = []

        if os.path.exists(feedback_file):
            with open(feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        feedback_item = json.loads(line.strip())
                        feedback_data.append(feedback_item)
                    except json.JSONDecodeError:
                        continue

        # Sort by timestamp (most recent first)
        feedback_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return jsonify({
            "total_feedback": len(feedback_data),
            "feedback": feedback_data
        })
    except Exception as e:
        logger.error(f"Error in admin_feedback: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/models/status', methods=['GET'])
@require_basic_auth
def admin_model_status():
    """Get current model status and versions"""
    try:
        from services.ml_detector import detector
        from services.email_text_detector import email_detector

        # Get URL model info
        url_versions = detector.list_versions()
        url_current = detector.current_version
        url_loaded = detector.model is not None

        # Get email model info
        email_versions = email_detector.list_versions()
        email_current = email_detector.current_version
        email_loaded = email_detector.model is not None

        # Get training history
        training_history = []
        metadata_file = 'data/training_metadata.jsonl'
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        training_history.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            training_history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return jsonify({
            "url_model": {
                "current_version": url_current,
                "loaded": url_loaded,
                "available_versions": url_versions
            },
            "email_model": {
                "current_version": email_current,
                "loaded": email_loaded,
                "available_versions": email_versions
            },
            "training_history": training_history[:10]  # Last 10 training sessions
        })
    except Exception as e:
        logger.error(f"Error in admin_model_status: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/models/switch', methods=['POST'])
@require_basic_auth
def admin_switch_model():
    """Switch to a different model version"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request data required"}), 400

        model_type = data.get('model_type')  # 'url' or 'email'
        version = data.get('version')

        if not model_type or not version:
            return jsonify({"error": "model_type and version are required"}), 400

        if model_type == 'url':
            from services.ml_detector import detector
            success = detector.switch_version(version)
            model_name = "URL model"
        elif model_type == 'email':
            from services.email_text_detector import email_detector
            success = email_detector.switch_version(version)
            model_name = "Email model"
        else:
            return jsonify({"error": "Invalid model_type. Must be 'url' or 'email'"}), 400

        if success:
            return jsonify({
                "message": f"Successfully switched {model_name} to version '{version}'",
                "model_type": model_type,
                "version": version
            })
        else:
            return jsonify({"error": f"Failed to switch {model_name} to version '{version}'"}), 500

    except Exception as e:
        logger.error(f"Error in admin_switch_model: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/admin/api/models/retrain', methods=['POST'])
@require_basic_auth
def admin_retrain_model():
    """Trigger model retraining"""
    try:
        import subprocess
        import threading

        def run_retraining():
            """Run retraining in background"""
            try:
                result = subprocess.run([
                    'python3', 'scripts/retrain_model.py'
                ], capture_output=True, text=True, cwd='.')

                logger.info(f"Retraining completed: {result.returncode}")
                if result.stdout:
                    logger.info(f"Retraining stdout: {result.stdout}")
                if result.stderr:
                    logger.error(f"Retraining stderr: {result.stderr}")

            except Exception as e:
                logger.error(f"Error in background retraining: {str(e)}")

        # Start retraining in background
        thread = threading.Thread(target=run_retraining, daemon=True)
        thread.start()

        return jsonify({
            "message": "Model retraining started in background",
            "status": "running"
        })

    except Exception as e:
        logger.error(f"Error starting retraining: {str(e)}")
        return jsonify({"error": "Failed to start retraining"}), 500

@app.before_request
def before_request():
    """Log incoming requests and start timing"""
    request.start_time = time.time()

@app.after_request
def after_request(response):
    """Log response details and timing"""
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        security_logger.log_api_request(
            method=request.method,
            endpoint=request.path,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', 'Unknown'),
            status_code=response.status_code,
            duration=duration
        )

    # Handle CORS
    origin = request.headers.get('Origin', '')
    response.headers['Access-Control-Allow-Origin'] = origin or '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-API-Key'
    response.headers['Access-Control-Allow-Credentials'] = 'true'

    return response

@app.errorhandler(500)
def handle_internal_error(error):
    """Handle internal server errors with detailed logging"""
    error_details = {
        "error_type": "InternalServerError",
        "message": str(error),
        "traceback": traceback.format_exc()
    }

    security_logger.log_error(
        error_type="InternalServerError",
        message=str(error),
        traceback=traceback.format_exc(),
        ip_address=getattr(request, 'remote_addr', 'Unknown'),
        endpoint=getattr(request, 'path', 'Unknown')
    )

    # Return different error details based on debug mode
    if app.config['DEBUG']:
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "details": error_details
        }), 500
    else:
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred while processing the request"
        }), 500

@app.errorhandler(400)
def handle_bad_request(error):
    """Handle bad request errors"""
    security_logger.log_security_event(
        event_type="BadRequest",
        details={"error": str(error)},
        ip_address=getattr(request, 'remote_addr', 'Unknown'),
        user_agent=getattr(request, 'headers', {}).get('User-Agent', 'Unknown'),
        endpoint=getattr(request, 'path', 'Unknown'),
        level='WARNING'
    )

    return jsonify({
        "error": "Bad request",
        "message": "Invalid request format or parameters"
    }), 400

@app.errorhandler(404)
def handle_not_found(error):
    """Handle 404 errors"""
    security_logger.log_security_event(
        event_type="NotFound",
        details={"path": getattr(request, 'path', 'Unknown')},
        ip_address=getattr(request, 'remote_addr', 'Unknown'),
        user_agent=getattr(request, 'headers', {}).get('User-Agent', 'Unknown'),
        endpoint=getattr(request, 'path', 'Unknown'),
        level='INFO'
    )

    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found"
    }), 404

@app.errorhandler(429)
def handle_rate_limit_exceeded(error):
    """Handle rate limit exceeded errors"""
    log_security_event("RATE_LIMIT_EXCEEDED", "Too many requests", getattr(request, 'remote_addr', 'Unknown'))
    return jsonify({
        "error": "Too many requests",
        "message": "Rate limit exceeded. Please try again later."
    }), 429

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Catch-all handler for unexpected errors"""
    error_details = {
        "error_type": type(error).__name__,
        "message": str(error),
        "traceback": traceback.format_exc()
    }

    security_logger.log_error(
        error_type="UnexpectedError",
        message=str(error),
        traceback=traceback.format_exc(),
        ip_address=getattr(request, 'remote_addr', 'Unknown'),
        endpoint=getattr(request, 'path', 'Unknown')
    )

    if app.config['DEBUG']:
        return jsonify({
            "error": "Unexpected error",
            "message": "An unexpected error occurred",
            "details": error_details
        }), 500
    else:
        return jsonify({
            "error": "Unexpected error",
            "message": "An unexpected error occurred while processing the request"
        }), 500

if __name__ == '__main__':
    app.run(debug=settings.debug, host=settings.host, port=settings.port)
