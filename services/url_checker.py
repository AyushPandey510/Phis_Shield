import os
import requests
import re
from typing import Tuple, List
from urllib.parse import urlparse
from virustotal_python import Virustotal
from utils.config import get_settings
from services.ml_detector import detector
from services.feature_extractor import extract_features
from services.ssl_checker import check_ssl

# Load configuration from settings
settings = get_settings()
GOOGLE_SAFE_BROWSING_API_KEY = settings.google_safe_browsing_api_key
VIRUSTOTAL_API_KEY = settings.virustotal_api_key
REQUEST_TIMEOUT = settings.request_timeout
MAX_REDIRECTS = settings.max_redirects

def check_url(url: str) -> Tuple[int, List[str]]:
    """
    Check URL risk using:
    1. Enhanced Heuristics
    2. Google Safe Browsing
    Returns (risk_score, details)
    """
    risk = 0
    details = []

    # Enhanced Heuristic checks
    # Suspicious patterns
    if re.search(r"--", url):
        risk += 15
        details.append("Suspicious: too many hyphens")

    # Suspicious TLDs
    suspicious_tlds = [".xyz", ".top", ".click", ".zip", ".club", ".online", ".site", ".space", ".website", ".tech"]
    if any(url.endswith(tld) for tld in suspicious_tlds):
        risk += 20
        details.append("Suspicious TLD")

    # IP address in URL
    if re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', url):
        risk += 25
        details.append("IP address in URL (suspicious)")

    # Too many subdomains
    domain_parts = url.split('.')
    if len(domain_parts) > 3:
        risk += 10
        details.append("Too many subdomains")

    # Common phishing keywords
    phishing_keywords = ['login', 'signin', 'verify', 'account', 'secure', 'banking', 'paypal', 'ebay', 'amazon']
    if any(keyword in url.lower() for keyword in phishing_keywords):
        risk += 15
        details.append("Contains common phishing keywords")

    # Shortened URLs - but exclude known legitimate domains that aren't actually shortened
    shortened_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 't.co', 'ow.ly', 'is.gd', 'lnkd.in', 'buff.ly', 'rebrand.ly']
    
    # Extract hostname to check against shortened domains
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    
    # Special case: chatgpt.com is not actually shortened despite the domain structure
    if hostname == 'chatgpt.com':
        # Not a shortened URL
        pass
    elif any(short_domain in hostname for short_domain in shortened_domains):
        risk += 20
        details.append("Shortened URL (cannot verify destination)")

    # Non-HTTPS
    if not url.startswith('https://'):
        risk += 10
        details.append("Not using HTTPS")

    # Google Safe Browsing (only if API key is set and valid)
    if GOOGLE_SAFE_BROWSING_API_KEY and GOOGLE_SAFE_BROWSING_API_KEY != "your-google-safe-browsing-api-key-here":
        gsb_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_API_KEY}"
        payload = {
            "client": {"clientId": "phishguard", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        try:
            r = requests.post(gsb_url, json=payload, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                response_data = r.json()
                if response_data.get("matches"):
                    risk += 50
                    details.append("🚨 FLAGGED BY GOOGLE SAFE BROWSING")
                else:
                    details.append("✅ URL not flagged by Google Safe Browsing")
            else:
                # Log more detailed error information
                error_details = f"GSB API error {r.status_code}"
                try:
                    error_response = r.json()
                    if "error" in error_response:
                        error_details += f": {error_response['error'].get('message', 'Unknown error')}"
                except:
                    error_details += f": {r.text[:200]}"  # First 200 chars of response
                details.append(error_details)
        except Exception as e:
            details.append(f"GSB check failed: {str(e)}")
    else:
        details.append("⚠️ Google Safe Browsing not configured (add API key to .env)")

    # VirusTotal URL Analysis (primary threat intelligence source)
    if VIRUSTOTAL_API_KEY and VIRUSTOTAL_API_KEY != "your-virustotal-api-key-here":
        try:
            # Initialize VirusTotal client
            vt = Virustotal(API_KEY=VIRUSTOTAL_API_KEY)

            # Get URL analysis - use the correct method for URL ID
            try:
                # Try different methods to get URL ID
                if hasattr(vt, 'get_url_id'):
                    url_id = vt.get_url_id(url)
                elif hasattr(vt, 'get_id'):
                    url_id = vt.get_id(url)
                else:
                    # Fallback: create URL ID manually
                    import base64
                    url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')

                resp = vt.request(f"urls/{url_id}")
            except Exception as method_error:
                # If URL ID methods fail, try to submit URL for analysis
                try:
                    submit_resp = vt.request("urls", data={"url": url}, method="POST")
                    if submit_resp.status_code == 200:
                        submit_data = submit_resp.json()
                        if "data" in submit_data:
                            url_id = submit_data["data"]["id"]
                            resp = vt.request(f"urls/{url_id}")
                        else:
                            raise Exception("No data in submission response")
                    else:
                        raise Exception(f"Submission failed: {submit_resp.status_code}")
                except Exception as submit_error:
                    raise Exception(f"Both URL ID generation and submission failed: {str(method_error)}, {str(submit_error)}")

            if resp.status_code == 200:
                vt_data = resp.json().get("data", {})
                attributes = vt_data.get("attributes", {})

                # Get analysis stats
                last_analysis_stats = attributes.get("last_analysis_stats", {})
                malicious = last_analysis_stats.get("malicious", 0)
                suspicious = last_analysis_stats.get("suspicious", 0)
                harmless = last_analysis_stats.get("harmless", 0)
                undetected = last_analysis_stats.get("undetected", 0)

                total_scans = malicious + suspicious + harmless + undetected

                if total_scans > 0:
                    malicious_percentage = (malicious / total_scans) * 100

                    if malicious > 0:
                        risk += 70  # High risk for any malicious detection
                        details.append(f"🚨 VIRUSTOTAL: {malicious}/{total_scans} engines detected as malicious")

                    if suspicious > 0:
                        risk += 30  # Medium risk for suspicious detection
                        details.append(f"⚠️ VIRUSTOTAL: {suspicious}/{total_scans} engines flagged as suspicious")

                    if malicious == 0 and suspicious == 0:
                        details.append(f"✅ VIRUSTOTAL: {harmless}/{total_scans} engines reported clean")
                    else:
                        details.append(f"📊 VIRUSTOTAL: Analyzed by {total_scans} engines")
                else:
                    details.append("ℹ️ VIRUSTOTAL: URL not yet analyzed")

            elif resp.status_code == 404:
                # URL not found in VirusTotal, submit for analysis
                try:
                    submit_resp = vt.request("urls", data={"url": url}, method="POST")
                    if submit_resp.status_code == 200:
                        details.append("📤 VIRUSTOTAL: URL submitted for analysis")
                    else:
                        details.append("⚠️ VIRUSTOTAL: Could not submit URL for analysis")
                except Exception as submit_error:
                    details.append(f"⚠️ VIRUSTOTAL: Submission failed - {str(submit_error)}")

            else:
                error_msg = f"VirusTotal API error {resp.status_code}"
                try:
                    error_data = resp.json()
                    if "error" in error_data:
                        error_msg += f": {error_data['error'].get('message', 'Unknown error')}"
                except:
                    pass
                details.append(f"⚠️ {error_msg}")

        except Exception as e:
            details.append(f"⚠️ VirusTotal check failed: {str(e)}")
    else:
        details.append("⚠️ VirusTotal not configured (add API key to .env)")

    # SSL Certificate Validation
    try:
        ssl_valid, ssl_details = check_ssl(url)
        if not ssl_valid:
            risk += 40  # High risk for invalid SSL
            details.append("🚨 SSL Certificate Invalid")
            # Add specific SSL issues
            if ssl_details.get('is_expired'):
                details.append("📅 SSL Certificate Expired")
            if ssl_details.get('is_self_signed'):
                details.append("🔒 Self-signed Certificate")
            if not ssl_details.get('subject'):
                details.append("❓ No Certificate Subject")
        else:
            details.append("✅ SSL Certificate Valid")
            # Bonus for valid SSL
            risk -= 5  # Slight reduction for valid SSL
    except Exception as e:
        details.append(f"⚠️ SSL check failed: {str(e)}")

    # Additional heuristic checks for better detection
    # Check for suspicious URL patterns
    if re.search(r'\d{4,}', url):  # Long numbers (potentially credit card numbers)
        risk += 15
        details.append("Contains long numeric sequences")

    if 'javascript:' in url.lower():
        risk += 30
        details.append("Contains JavaScript execution")

    if len(url) > 200:  # Very long URLs
        risk += 10
        details.append("Unusually long URL")

    # Extract external service analysis results for ML weighting
    gsb_flagged = "FLAGGED BY GOOGLE SAFE BROWSING" in " ".join(details)
    vt_malicious = "engines detected as malicious" in " ".join(details)
    vt_suspicious = "engines flagged as suspicious" in " ".join(details)
    ssl_invalid = "SSL Certificate Invalid" in " ".join(details)
    ssl_valid = "SSL Certificate Valid" in " ".join(details)
    vt_clean = "engines reported clean" in " ".join(details)
    vt_clean_count = 0
    vt_total_count = 0
    
    # Extract VirusTotal counts for better weighting
    vt_details_text = " ".join(details)
    if "VIRUSTOTAL:" in vt_details_text:
        clean_match = re.search(r'(\d+)/(\d+) engines reported clean', vt_details_text)
        if clean_match:
            vt_clean_count = int(clean_match.group(1))
            vt_total_count = int(clean_match.group(2))
    
    # Add ML-based detection with sophisticated external service weighting
    try:
        features = extract_features(url)
        ml_prob = detector.predict(features)
        
        # Parse hostname for domain analysis
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        
        # Extended list of known safe domains
        safe_domains = [
            'google.com', 'microsoft.com', 'apple.com', 'amazon.com', 'facebook.com',
            'twitter.com', 'linkedin.com', 'github.com', 'gitlab.com', 'bitbucket.org',
            'devfolio.co', 'hackerearth.com', 'hackerrank.com', 'leetcode.com',
            'stackoverflow.com', 'medium.com', 'youtube.com', 'reddit.com',
            'chatgpt.com', 'openai.com', 'anthropic.com', 'claude.ai', 'perplexity.ai',
            'wikipedia.org', 'wikimedia.org', 'archive.org', 'mit.edu', 'stanford.edu',
            'harvard.edu', ' berkeley.edu', 'cmu.edu', 'cornell.edu', 'princeton.edu'
        ]

        is_safe_domain = any(safe_domain in hostname for safe_domain in safe_domains)
        
        # Calculate external service consensus score (-1 to 1, where -1 = all malicious, 0 = mixed, 1 = all clean)
        external_consensus_score = 1.0  # Start optimistic (1.0 = all clean)
        services_checked = 0
        threat_indicators = 0
        
        if gsb_flagged:
            external_consensus_score = -1.0  # Google flagged = all malicious
            threat_indicators += 1
        elif "URL not flagged by Google Safe Browsing" in " ".join(details):
            external_consensus_score *= 0.8  # Google clean but not definitive
            services_checked += 1
            
        if ssl_invalid:
            external_consensus_score -= 0.5  # SSL invalid reduces consensus
            threat_indicators += 1
        elif ssl_valid:
            external_consensus_score *= 0.9  # SSL valid is good signal
            services_checked += 1
            
        if vt_malicious:
            external_consensus_score = -1.0  # VirusTotal malicious = all malicious
            threat_indicators += 1
        elif vt_suspicious:
            external_consensus_score -= 0.3  # VirusTotal suspicious reduces consensus
            threat_indicators += 1
        elif vt_total_count > 0:
            # Calculate VirusTotal consensus (clean engines / total engines)
            vt_consensus = vt_clean_count / vt_total_count
            if vt_consensus > 0.8:
                external_consensus_score *= vt_consensus  # Mostly clean
                services_checked += 1
            elif vt_consensus < 0.2:
                external_consensus_score *= -vt_consensus  # Mostly malicious
                threat_indicators += 1
            else:
                external_consensus_score *= (vt_consensus - 0.5) * 2  # Mixed results
        elif "engines reported clean" in " ".join(details):
            external_consensus_score *= 0.7  # Some clean but not quantified
            services_checked += 1
            
        # Special case: shortened URLs shouldn't be flagged if other signals are clean
        is_shortened = "Shortened URL" in " ".join(details)
        
        # Calculate final ML weight based on external consensus and domain reputation
        if is_safe_domain:
            if external_consensus_score > 0.5:  # Safe domain + clean external signals
                ml_weight = 0.05  # Very low weight - trust external consensus
            elif external_consensus_score < -0.3:  # Safe domain + threat signals
                ml_weight = 0.3   # Higher weight to investigate potential compromise
            else:
                ml_weight = 0.15   # Moderate weight for mixed signals
        else:
            # Unknown domain - weight based on external consensus
            if external_consensus_score > 0.6:  # Strong external consensus for safety
                ml_weight = 0.1   # Reduce ML influence when external services agree it's safe
            elif external_consensus_score < -0.3:  # External signals suggest risk
                ml_weight = 0.6   # Higher ML influence to help confirm threats
            else:  # Mixed external signals
                ml_weight = 0.3   # Moderate ML influence
                
        # Special handling for shortened URLs with clean external signals
        if is_shortened and external_consensus_score > 0.5:
            ml_weight = 0.1  # Don't let ML flag shortened URLs if external services are clean
            
        # Calculate ML contribution
        ml_risk_contribution = int(ml_prob * 50 * ml_weight)  # Reduced max contribution
        
        # Only add ML risk if it makes sense with external consensus
        should_add_ml_risk = False
        
        if ml_prob >= 0.9 and external_consensus_score < -0.2:  # High ML + threatening external
            should_add_ml_risk = True
        elif ml_prob >= 0.7 and external_consensus_score < 0.3:  # Med-high ML + mixed external  
            should_add_ml_risk = True
        elif not is_safe_domain and ml_prob >= 0.8 and services_checked == 0:  # High ML + no external checks
            should_add_ml_risk = True
            
        if should_add_ml_risk:
            risk += ml_risk_contribution
            
        # Calculate final ML confidence based on both ML prediction and external consensus
        # Convert external consensus from (-1 to 1) scale to (0 to 1) scale for combination
        if external_consensus_score >= 0:
            # Safe external signals - reduce ML confidence proportionally
            final_ml_confidence = ml_prob * (1.0 - external_consensus_score * 0.7)
        else:
            # Threat external signals - boost ML confidence
            final_ml_confidence = min(1.0, ml_prob + abs(external_consensus_score) * 0.3)
        
        # Show appropriate ML detail message based on final confidence
        if final_ml_confidence >= 0.7:
            details.append(f"🤖 ML Model: High phishing probability ({final_ml_confidence:.1%})")
        elif final_ml_confidence >= 0.4:
            details.append(f"⚠️ ML Model: Moderate phishing probability ({final_ml_confidence:.1%})")
        elif final_ml_confidence >= 0.2:
            details.append(f"🤖 ML Model: Suspicious patterns detected ({final_ml_confidence:.1%})")
        elif final_ml_confidence >= 0.1:
            details.append(f"🤖 ML Model: Low phishing probability ({final_ml_confidence:.1%})")
        else:
            # Very low final confidence - provide context
            if is_safe_domain and external_consensus_score > 0.7:
                details.append(f"✅ ML Model: Patterns consistent with trusted domain ({final_ml_confidence:.1%})")
            elif external_consensus_score > 0.8:
                details.append(f"✅ ML Model: Low risk despite patterns ({final_ml_confidence:.1%})")
            elif is_shortened and external_consensus_score > 0.7:
                details.append(f"🤖 ML Model: Shortened URL patterns detected but external signals clean ({final_ml_confidence:.1%})")
            else:
                details.append(f"🤖 ML Model: Very low phishing probability ({final_ml_confidence:.1%})")

    except Exception as e:
        details.append(f"⚠️ ML analysis failed: {str(e)}")

    # Final rule-based risk assessment with ML consideration
    if gsb_flagged:
        risk = max(risk, 80)  # Google Safe Browsing is authoritative
        details.append("🚨 BLOCKED: Google Safe Browsing threat detection")
    elif vt_malicious:
        risk = max(risk, 75)  # VirusTotal malicious detection
        details.append("🚨 HIGH RISK: Multiple antivirus engines flagged as malicious")
    elif ssl_invalid:
        risk = max(risk, 60)  # Invalid SSL is a strong indicator
        details.append("🚨 SSL ISSUES: Certificate problems detected")
    elif vt_suspicious:
        risk = max(risk, 50)  # VirusTotal suspicious
        details.append("⚠️ MEDIUM RISK: Some security engines flagged as suspicious")

    # Ensure minimum risk for obviously suspicious sites
    final_risk = min(max(0, risk), 100)

    # Add risk level interpretation
    if final_risk >= 70:
        details.insert(0, "🔴 HIGH RISK - Exercise extreme caution!")
    elif final_risk >= 40:
        details.insert(0, "🟡 MEDIUM RISK - Proceed with caution")
    elif final_risk >= 20:
        details.insert(0, "🟢 LOW RISK - Generally safe")
    else:
        details.insert(0, "🟢 VERY LOW RISK - Appears safe")

    return final_risk, details
