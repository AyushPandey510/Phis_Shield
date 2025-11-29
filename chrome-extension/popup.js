// DOM elements
const urlInput = document.getElementById('url-input');
const getCurrentUrlBtn = document.getElementById('get-current-url');
const checkUrlBtn = document.getElementById('check-url-btn');
const checkSslBtn = document.getElementById('check-ssl-btn');
const expandLinkBtn = document.getElementById('expand-link-btn');
const checkBreachBtn = document.getElementById('check-breach-btn');
const submitBreachBtn = document.getElementById('submit-breach-btn');
const breachInputs = document.getElementById('breach-inputs');
const emailInput = document.getElementById('email-input');
const passwordInput = document.getElementById('password-input');
const loading = document.getElementById('loading');
const results = document.getElementById('results');
const resultsContent = document.getElementById('results-content');
const errorDiv = document.getElementById('error');
const errorMessage = document.querySelector('.error-message');


// Feedback elements
const feedbackSection = document.getElementById('feedback-section');
const feedbackCorrectBtn = document.getElementById('feedback-correct');
const feedbackIncorrectBtn = document.getElementById('feedback-incorrect');
const feedbackDetails = document.getElementById('feedback-details');
const feedbackUrlType = document.getElementById('feedback-url-type');
const submitFeedbackBtn = document.getElementById('submit-feedback');
const feedbackThanks = document.getElementById('feedback-thanks');

// Settings elements
const warningEnabledCheckbox = document.getElementById('warning-enabled');
const warningSensitivitySelect = document.getElementById('warning-sensitivity');

// Global variables for feedback
let currentFeedbackData = null;

// User ID for tracking
let userId = null;

// API base URL - configurable for different environments
const API_BASE = 'http://localhost:5000'; // Updated to match development server

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
    console.log('PhisGuard: Popup loaded with updated code');
    await initializeUserId();
    getCurrentTabUrl();
    loadWarningSettings();
    setupEventListeners();
});

// Initialize user ID for persistent tracking across devices
async function initializeUserId() {
    try {
        // For development/local testing, use IP address as user ID
        // In production, this would be a proper user identifier
        userId = '127.0.0.1'; // Local development IP

        // Store it for consistency
        await chrome.storage.local.set({ phisguard_user_id: userId });
        console.log('PhisGuard: Using user ID for local development:', userId);
    } catch (error) {
        console.error('Error initializing user ID:', error);
        // Fallback to IP address
        userId = '127.0.0.1';
    }
}

// Generate a unique user ID
function generateUserId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 9);
    return 'pg_' + timestamp + '_' + random;
}

// Get current tab URL
async function getCurrentTabUrl() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab && tab.url) {
            urlInput.value = tab.url;
        }
    } catch (error) {
        console.error('Error getting current tab URL:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    getCurrentUrlBtn.addEventListener('click', getCurrentTabUrl);
    checkUrlBtn.addEventListener('click', () => performCheck('url'));
    checkSslBtn.addEventListener('click', () => performCheck('ssl'));
    expandLinkBtn.addEventListener('click', () => performCheck('link'));
    checkBreachBtn.addEventListener('click', () => {
        breachInputs.classList.toggle('hidden');
    });
    submitBreachBtn.addEventListener('click', () => performCheck('breach'));


    // Feedback event listeners
    feedbackCorrectBtn.addEventListener('click', () => handleFeedback(true));
    feedbackIncorrectBtn.addEventListener('click', () => handleFeedback(false));
    submitFeedbackBtn.addEventListener('click', submitFeedback);

    // Settings event listeners
    warningEnabledCheckbox.addEventListener('change', saveWarningSettings);
    warningSensitivitySelect.addEventListener('change', saveWarningSettings);
}

// Perform security check
async function performCheck(type) {
    showLoading();
    hideResults();
    hideError();

    try {
        let endpoint, data;

        switch (type) {
            case 'url':
                const url = urlInput.value.trim();
                if (!url) {
                    showError('Please enter a URL');
                    hideLoading();
                    return;
                }
                endpoint = '/check-url';
                data = { url };
                break;
            case 'ssl':
                const sslUrl = urlInput.value.trim();
                if (!sslUrl) {
                    showError('Please enter a URL');
                    hideLoading();
                    return;
                }
                endpoint = '/check-ssl';
                data = { url: sslUrl };
                break;
            case 'link':
                const linkUrl = urlInput.value.trim();
                if (!linkUrl) {
                    showError('Please enter a URL');
                    hideLoading();
                    return;
                }
                endpoint = '/expand-link';
                data = { url: linkUrl };
                break;
            case 'breach':
                console.log('PhisGuard: Starting breach check');
                endpoint = '/check-breach';
                const emailValue = emailInput.value.trim();
                const passwordValue = passwordInput.value.trim();
                console.log('PhisGuard: Email value:', emailValue ? 'present' : 'empty');
                console.log('PhisGuard: Password value:', passwordValue ? 'present' : 'empty');
                data = {};

                if (emailValue) {
                    data.email = emailValue;
                }
                if (passwordValue) {
                    data.password = passwordValue;
                }

                console.log('PhisGuard: Request data:', data);

                // For testing, use a valid email if example.com is used
                if (data.email && data.email.includes('@example.com')) {
                    data.email = data.email.replace('@example.com', '@test.com');
                    console.log('PhisGuard: Updated email for testing:', data.email);
                }

                if (!emailValue && !passwordValue) {
                    console.log('PhisGuard: No email or password provided');
                    showError('Please enter email or password for breach check');
                    hideLoading();
                    return;
                }
                break;
            default:
                throw new Error('Unknown check type');
        }

        // Add user ID to the request for tracking
        const requestData = { ...data };
        if (userId) {
            requestData.user_id = userId;
        }

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'a0c674401be58be8eb1929239742b625'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        displayResults(type, result);

    } catch (error) {
        console.error('Error performing check:', error);
        showError(error.message || 'An error occurred while performing the check');
    } finally {
        hideLoading();
    }
}

// Display results
function displayResults(type, data) {
    let html = '';

    switch (type) {
        case 'url':
            const riskClass = getRiskClass(data.recommendation);
            const riskPercentage = data.risk_score;
            const riskBarWidth = riskPercentage;
            const riskBarColor = riskPercentage >= 70 ? '#e74c3c' : riskPercentage >= 40 ? '#f39c12' : '#27ae60';

            // Safely handle details array
            const detailsHtml = (data.details && Array.isArray(data.details) && data.details.length > 0)
                ? `<ul>${data.details.map(detail => `<li>${detail}</li>`).join('')}</ul>`
                : '<p>No analysis details available</p>';

            html = `
                <div class="result-item">
                    <strong>URL:</strong> ${data.url}<br>
                    <div class="risk-score-container">
                        <strong>Risk Score:</strong>
                        <div class="risk-score-bar">
                            <div class="risk-score-fill" style="width: ${riskBarWidth}%; background-color: ${riskBarColor};"></div>
                            <span class="risk-score-text">${riskPercentage}/100</span>
                        </div>
                    </div>
                    <strong>Recommendation:</strong> <span class="${riskClass}">${data.recommendation.toUpperCase()}</span><br>
                    <div class="details-section">
                        <strong>Analysis Details:</strong>
                        ${detailsHtml}
                    </div>
                </div>
            `;
            break;
        case 'ssl':
            const sslDetails = data.details || {};
            const sslRiskFlags = sslDetails.risk_flags || [];
            const sslRiskScore = sslDetails.risk_score || 0;
            const sslRiskBarColor = sslRiskScore >= 70 ? '#e74c3c' : sslRiskScore >= 40 ? '#f39c12' : '#27ae60';
            const connectionType = sslDetails.connection_type || 'https';

            html = `
                <div class="result-item">
                    <strong>URL:</strong> ${data.url}<br>
                    <strong>Connection:</strong> ${connectionType.toUpperCase()}<br>
                    ${connectionType === 'https' ? `
                        <strong>SSL Valid:</strong> ${data.ssl_valid ? '✅ Yes' : '❌ No'}<br>
                        <div class="risk-score-container">
                            <strong>SSL Risk Score:</strong>
                            <div class="risk-score-bar">
                                <div class="risk-score-fill" style="width: ${sslRiskScore}%; background-color: ${sslRiskBarColor};"></div>
                                <span class="risk-score-text">${sslRiskScore}/100</span>
                            </div>
                        </div>
                        ${sslDetails.subject ? `<strong>Subject:</strong> ${sslDetails.subject.commonName || 'N/A'}<br>` : ''}
                        ${sslDetails.issuer ? `<strong>Issuer:</strong> ${sslDetails.issuer.commonName || 'N/A'}<br>` : ''}
                        ${sslDetails.days_until_expiry !== undefined ? `<strong>Days until expiry:</strong> ${sslDetails.days_until_expiry}<br>` : ''}
                        ${sslDetails.is_expired !== undefined ? `<strong>Status:</strong> ${sslDetails.is_expired ? '❌ EXPIRED' : '✅ Valid'}<br>` : ''}
                        ${sslDetails.is_wildcard !== undefined ? `<strong>Wildcard:</strong> ${sslDetails.is_wildcard ? '⚠️ Yes' : '✅ No'}<br>` : ''}
                        ${sslDetails.is_self_signed !== undefined ? `<strong>Self-signed:</strong> ${sslDetails.is_self_signed ? '🚨 Yes' : '✅ No'}<br>` : ''}
                    ` : ''}
                    ${sslRiskFlags.length > 0 ? `
                        <div class="risk-flags">
                            <strong>🔍 SSL Analysis:</strong>
                            <ul>
                                ${sslRiskFlags.map(flag => `<li>${flag}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            `;
            break;
        case 'link':
            const analysis = data.analysis || {};
            const riskFlags = analysis.risk_flags || [];
            const formattedChain = analysis.formatted_chain || `${data.original_url} → ${data.final_url}`;

            html = `
                <div class="result-item">
                    <strong>Original URL:</strong> ${data.original_url}<br>
                    <strong>Final URL:</strong> ${data.final_url}<br>
                    <strong>Redirect Count:</strong> ${data.redirect_count}<br>
                    <div class="redirect-chain">
                        <strong>Redirect Chain:</strong><br>
                        <div class="chain-display">${formattedChain}</div>
                    </div>
                    ${riskFlags.length > 0 ? `
                        <div class="risk-flags">
                            <strong>⚠️ Security Analysis:</strong>
                            <ul>
                                ${riskFlags.map(flag => `<li>${flag}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    ${analysis.suspicious ? '<div class="suspicious-warning">🚨 Suspicious redirect pattern detected!</div>' : ''}
                </div>
            `;
            break;
        case 'breach':
            html = `
                <div class="result-item">
                    ${data.password_check ? `
                        <strong>Password Breach:</strong> ${data.password_check.breached ? 'Yes' : 'No'}<br>
                        <strong>Breach Count:</strong> ${data.password_check.breach_count}<br>
                    ` : ''}
                    ${data.password_strength ? `
                        <strong>Password Strength Score:</strong> ${data.password_strength.score}/100<br>
                        <strong>Feedback:</strong> ${JSON.stringify(data.password_strength.feedback, null, 2)}<br>
                    ` : ''}
                    ${data.email_check ? `
                        <strong>Email Breach:</strong> ${data.email_check.breached ? 'Yes' : 'No'}<br>
                        <strong>Breach Count:</strong> ${data.email_check.breach_count}<br>
                    ` : ''}
                </div>
            `;
            break;
    }

    resultsContent.innerHTML = html;

    // Show feedback section for URL checks
    if (type === 'url') {
        currentFeedbackData = {
            url: data.url,
            risk_score: data.risk_score,
            recommendation: data.recommendation,
            timestamp: new Date().toISOString()
        };
        showFeedbackSection();
    } else {
        hideFeedbackSection();
    }

    showResults();
}

// Get risk class for color coding
function getRiskClass(recommendation) {
    switch (recommendation) {
        case 'safe':
            return 'risk-safe';
        case 'caution':
            return 'risk-caution';
        case 'danger':
            return 'risk-danger';
        default:
            return '';
    }
}

// Feedback functions
function showFeedbackSection() {
    feedbackSection.classList.remove('hidden');
    feedbackDetails.classList.add('hidden');
    feedbackThanks.classList.add('hidden');
    feedbackCorrectBtn.disabled = false;
    feedbackIncorrectBtn.disabled = false;
}

function hideFeedbackSection() {
    feedbackSection.classList.add('hidden');
}

function handleFeedback(isCorrect) {
    if (!currentFeedbackData) return;

    currentFeedbackData.is_correct = isCorrect;
    currentFeedbackData.user_feedback = isCorrect;

    if (isCorrect) {
        // If correct, submit immediately
        submitFeedbackData(currentFeedbackData);
    } else {
        // If incorrect, show details form
        feedbackDetails.classList.remove('hidden');
        feedbackCorrectBtn.disabled = true;
        feedbackIncorrectBtn.disabled = true;
    }
}

async function submitFeedback() {
    if (!currentFeedbackData) return;

    const urlType = feedbackUrlType.value;
    if (!urlType) {
        showError('Please select the type of site');
        return;
    }

    currentFeedbackData.corrected_label = urlType;
    currentFeedbackData.user_correction = urlType;

    await submitFeedbackData(currentFeedbackData);
}

async function submitFeedbackData(feedbackData) {
    try {
        showLoading();

        // Add user ID to feedback data for tracking
        const feedbackWithUserId = {
            ...feedbackData,
            user_id: userId,
            extension_user_id: userId
        };

        const response = await fetch(`${API_BASE}/submit-feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'a0c674401be58be8eb1929239742b625'
            },
            body: JSON.stringify(feedbackWithUserId)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Feedback submitted successfully:', result);

        // Show thank you message
        feedbackDetails.classList.add('hidden');
        feedbackThanks.classList.remove('hidden');
        feedbackCorrectBtn.disabled = true;
        feedbackIncorrectBtn.disabled = true;

    } catch (error) {
        console.error('Error submitting feedback:', error);
        showError('Failed to submit feedback. Please try again.');
    } finally {
        hideLoading();
    }
}

// UI state management
function showLoading() {
    loading.classList.remove('hidden');
}

function hideLoading() {
    loading.classList.add('hidden');
}

function showResults() {
    results.classList.remove('hidden');
}

function hideResults() {
    results.classList.add('hidden');
}

function showError(message) {
    errorMessage.textContent = message;
    errorDiv.classList.remove('hidden');
}

function hideError() {
    errorDiv.classList.add('hidden');
}

// Settings management functions
function loadWarningSettings() {
    chrome.storage.local.get(['warningEnabled', 'warningSensitivity'], (result) => {
        warningEnabledCheckbox.checked = result.warningEnabled !== false; // Default to true
        warningSensitivitySelect.value = result.warningSensitivity || 'medium'; // Default to medium
    });
}

function saveWarningSettings() {
    const settings = {
        warningEnabled: warningEnabledCheckbox.checked,
        warningSensitivity: warningSensitivitySelect.value
    };

    chrome.storage.local.set(settings, () => {
        console.log('PhisGuard: Warning settings saved', settings);
    });
}

