import re
import numpy as np
from urllib.parse import urlparse
from typing import Dict

def log1p(x):
    """Safe log1p function"""
    return np.log(1 + x)

def cap(x, max_val):
    """Cap value at maximum"""
    return x if x < max_val else max_val

def safe_feature(val, max_val):
    """Apply log1p and cap"""
    return log1p(cap(val, max_val))

def extract_features(url: str) -> Dict[str, float]:
    """
    Extract features from URL for ML model.
    Matches the feature extraction from the JS version.
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
    except:
        # Return safe defaults for invalid URLs
        return {
            'url_length': 0,
            'domain_length': 0,
            'subdomain_length': 0,
            'tld_length': 0,
            'path_length': 0,
            'query_length': 0,
            'num_dots': 0,
            'num_hyphens': 0,
            'num_slashes': 0,
            'num_question': 0,
            'num_equals': 0,
            'num_at': 0,
            'num_percent': 0,
            'num_digits': 0,
            'has_https': 1,
            'kw_login': 0,
            'kw_secure': 0,
            'kw_update': 0,
            'kw_verify': 0,
            'kw_payment': 0,
            'kw_account': 0,
        }

    # Extract components
    hostname = parsed.hostname or ""
    pathname = parsed.path or ""
    search = parsed.query or ""

    # Parse hostname parts
    parts = hostname.split(".")
    domain = parts[-2] if len(parts) >= 2 else hostname
    subdomain = ".".join(parts[:-2]) if len(parts) > 2 else ""
    tld = parts[-1] if len(parts) >= 2 else ""

    # Raw counts
    raw_url_len = len(url)
    raw_path_len = len(pathname)
    raw_query_len = len(search)

    raw_digits = len(re.findall(r'[0-9]', url))
    raw_dots = url.count('.')
    raw_hyphens = url.count('-')
    raw_slashes = url.count('/')
    raw_question = url.count('?')
    raw_equals = url.count('=')
    raw_at = url.count('@')
    raw_percent = url.count('%')

    lower_url = url.lower()

    # Apply safe feature transformation
    features = {
        'url_length': safe_feature(raw_url_len, 2000),
        'domain_length': safe_feature(len(domain), 200),
        'subdomain_length': safe_feature(len(subdomain), 200),
        'tld_length': safe_feature(len(tld), 50),
        'path_length': safe_feature(raw_path_len, 2000),
        'query_length': safe_feature(raw_query_len, 2000),
        'num_dots': safe_feature(raw_dots, 50),
        'num_hyphens': safe_feature(raw_hyphens, 50),
        'num_slashes': safe_feature(raw_slashes, 200),
        'num_question': safe_feature(raw_question, 20),
        'num_equals': safe_feature(raw_equals, 50),
        'num_at': safe_feature(raw_at, 10),
        'num_percent': safe_feature(raw_percent, 20),
        'num_digits': safe_feature(raw_digits, 200),
        'has_https': 1.0 if lower_url.startswith('https') else 0.0,
        'kw_login': 1.0 if 'login' in lower_url else 0.0,
        'kw_secure': 1.0 if 'secure' in lower_url else 0.0,
        'kw_update': 1.0 if 'update' in lower_url else 0.0,
        'kw_verify': 1.0 if 'verify' in lower_url else 0.0,
        'kw_payment': 1.0 if 'payment' in lower_url else 0.0,
        'kw_account': 1.0 if 'account' in lower_url else 0.0,
    }

    return features