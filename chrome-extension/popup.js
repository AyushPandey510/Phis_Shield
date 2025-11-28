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

// Dashboard elements
const dashboardBtn = document.getElementById('dashboard-btn');
const dashboard = document.getElementById('dashboard');
const refreshDashboardBtn = document.getElementById('refresh-dashboard');
const downloadReportBtn = document.getElementById('download-report');
const backToMainBtn = document.getElementById('back-to-main');
const protectedCount = document.getElementById('protected-count');
const riskStats = document.getElementById('risk-stats');
const weeklyChecks = document.getElementById('weekly-checks');
const recentDetections = document.getElementById('recent-detections');
const securityTimeline = document.getElementById('security-timeline');

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

// WebSocket/Socket.IO connection
let socket = null;
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
    initializeWebSocket();
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

    // Dashboard event listeners
    dashboardBtn.addEventListener('click', showDashboard);
    refreshDashboardBtn.addEventListener('click', loadDashboardData);
    downloadReportBtn.addEventListener('click', downloadSecurityReport);
    backToMainBtn.addEventListener('click', hideDashboard);

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
                        <ul>
                            ${data.details.map(detail => `<li>${detail}</li>`).join('')}
                        </ul>
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

// Dashboard functions
async function showDashboard() {
    // Hide main interface
    document.querySelector('.container > header').classList.add('hidden');
    document.querySelector('.url-section').classList.add('hidden');
    document.querySelector('.buttons-section').classList.add('hidden');
    document.querySelector('.settings-section').classList.add('hidden');
    document.getElementById('breach-inputs').classList.add('hidden');
    loading.classList.add('hidden');
    results.classList.add('hidden');
    errorDiv.classList.add('hidden');

    // Show dashboard
    dashboard.classList.remove('hidden');

    // Load any pending detections from storage
    loadPendingDetections();

    // Load dashboard data
    await loadDashboardData();
}

function hideDashboard() {
    // Hide dashboard
    dashboard.classList.add('hidden');

    // Show main interface
    document.querySelector('.container > header').classList.remove('hidden');
    document.querySelector('.url-section').classList.remove('hidden');
    document.querySelector('.buttons-section').classList.remove('hidden');
    document.querySelector('.settings-section').classList.remove('hidden');
}

async function loadDashboardData() {
    try {
        showLoading();

        // Fetch user security data from backend with user ID
        const url = userId ? `${API_BASE}/user/security-dashboard?user_id=${encodeURIComponent(userId)}` : `${API_BASE}/user/security-dashboard`;
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'a0c674401be58be8eb1929239742b625'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayDashboardData(data);

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showError('Failed to load dashboard data. Please try again.');
    } finally {
        hideLoading();
    }
}

function displayDashboardData(data) {
    // Update statistics
    protectedCount.textContent = data.protected_count || 0;
    document.getElementById('high-risk').textContent = data.high_risk_count || 0;
    document.getElementById('medium-risk').textContent = data.medium_risk_count || 0;
    document.getElementById('low-risk').textContent = data.low_risk_count || 0;
    weeklyChecks.textContent = data.weekly_checks || 0;

    // Update recent detections
    const detectionsHtml = (data.recent_detections || []).map(detection => `
        <div class="detection-item">
            <div class="url">${detection.url}</div>
            <div class="details">
                <span>${new Date(detection.timestamp).toLocaleDateString()}</span>
                <span class="risk-level ${detection.risk_level}">${detection.risk_level}</span>
            </div>
        </div>
    `).join('');

    recentDetections.innerHTML = detectionsHtml || '<div class="loading">No recent detections found</div>';

    // Update security timeline
    const timelineHtml = (data.security_timeline || []).map(event => `
        <div class="timeline-item">
            <div class="time">${new Date(event.timestamp).toLocaleString()}</div>
            <div class="event">${event.event}</div>
        </div>
    `).join('');

    securityTimeline.innerHTML = timelineHtml || '<div class="loading">No security events found</div>';

    // Update threat chart (simplified version)
    updateThreatChart(data.threat_categories || {});
}

function updateThreatChart(categories) {
    // Simple text-based chart for now
    const chartContainer = document.getElementById('threatChart').parentElement;
    const chartHtml = Object.entries(categories).map(([category, count]) => `
        <div style="margin: 5px 0;">
            <span style="display: inline-block; width: 120px;">${category}:</span>
            <span style="display: inline-block; width: ${Math.min(count * 10, 100)}px; background: #3498db; color: white; text-align: center; border-radius: 3px;">${count}</span>
        </div>
    `).join('');

    document.getElementById('threatChart').style.display = 'none';
    chartContainer.innerHTML += '<div style="padding: 10px;">' + (chartHtml || 'No threat data available') + '</div>';
}

async function downloadSecurityReport() {
    try {
        showLoading();
        console.log('🔍 Checking jsPDF availability...');

        // Check if jsPDF is properly loaded
        if (!window.jspdf) {
            console.error('❌ jsPDF not found! Loading it now...');
            await loadJSPDFLibrary();
        }

        console.log('✅ jsPDF is available:', !!window.jspdf);

        const url = userId ? `${API_BASE}/user/security-report?user_id=${encodeURIComponent(userId)}` : `${API_BASE}/user/security-report`;
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'dev-api-key-change-this-in-production-1234567890123456'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Force PDF generation without fallback to see the actual error
        console.log('🔄 Attempting PDF generation...');
        await generateAndDownloadPDF(data);

    } catch (error) {
        console.error('❌ Error in downloadSecurityReport:', error);
        
        // If PDF fails, show specific error and don't fallback to TXT
        if (error.message.includes('PDF') || error.message.includes('jsPDF')) {
            showError('PDF generation failed: ' + error.message);
        } else {
            showError('Failed to download security report: ' + error.message);
        }
    } finally {
        hideLoading();
    }
}

// Function to dynamically load jsPDF
function loadJSPDFLibrary() {
    return new Promise((resolve, reject) => {
        if (window.jspdf) {
            resolve();
            return;
        }

        console.log('📥 Loading jsPDF from CDN...');
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        
        script.onload = () => {
            console.log('✅ jsPDF loaded successfully');
            // Wait a bit for the library to initialize
            setTimeout(() => {
                if (window.jspdf) {
                    resolve();
                } else {
                    reject(new Error('jsPDF not available after loading'));
                }
            }, 100);
        };
        
        script.onerror = () => {
            console.error('❌ Failed to load jsPDF');
            reject(new Error('Failed to load PDF library from CDN'));
        };
        
        document.head.appendChild(script);
    });
}

async function downloadSecurityReport() {
    try {
        showLoading();

        // DIRECT CHECK - No CDN loading attempts
        if (!window.jspdf) {
            throw new Error(
                'jsPDF is not loaded. Please add this line to your HTML file:\n\n' +
                '<script src="jspdf.umd.min.js"></script>\n\n' +
                'Make sure the file is in the same folder as your HTML file.'
            );
        }

        const url = userId ? `${API_BASE}/user/security-report?user_id=${encodeURIComponent(userId)}` : `${API_BASE}/user/security-report`;
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'dev-api-key-change-this-in-production-1234567890123456'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Generate PDF using local jsPDF
        generateSecurityReportPDF(data);

    } catch (error) {
        console.error('Error downloading report:', error);
        showError(error.message);
    } finally {
        hideLoading();
    }
}

function generateSecurityReportPDF(data) {
    try {
        // Direct access to local jsPDF - no CDN
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        let yPos = 20;
        const margin = 20;
        const pageWidth = doc.internal.pageSize.width;

        // Header
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.text('PHISGUARD SECURITY REPORT', pageWidth / 2, yPos, { align: 'center' });
        yPos += 10;
        
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text(`Generated: ${new Date().toLocaleString()}`, pageWidth / 2, yPos, { align: 'center' });
        yPos += 20;

        // Security Statistics
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.text('SECURITY STATISTICS', margin, yPos);
        yPos += 10;
        
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        
        const stats = [
            `URLs Protected: ${data.protected_count || 0}`,
            `High Risk Detections: ${data.high_risk_count || 0}`,
            `Medium Risk Detections: ${data.medium_risk_count || 0}`,
            `Low Risk Detections: ${data.low_risk_count || 0}`,
            `Weekly Security Checks: ${data.weekly_checks || 0}`
        ];
        
        stats.forEach(stat => {
            doc.text(stat, margin, yPos);
            yPos += 7;
        });

        yPos += 10;

        // Recent Detections
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.text('RECENT DETECTIONS', margin, yPos);
        yPos += 10;
        
        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        
        const recentDetections = data.recent_detections || [];
        if (recentDetections.length === 0) {
            doc.text('No recent detections found.', margin, yPos);
        } else {
            recentDetections.forEach(detection => {
                if (yPos > 270) {
                    doc.addPage();
                    yPos = margin;
                }
                
                const text = `${detection.timestamp}: ${detection.url} (${detection.risk_level})`;
                const lines = doc.splitTextToSize(text, pageWidth - (margin * 2));
                
                lines.forEach(line => {
                    doc.text(line, margin, yPos);
                    yPos += 5;
                });
                yPos += 2;
            });
        }

        // Save PDF
        const fileName = `phisguard-security-report-${new Date().toISOString().split('T')[0]}.pdf`;
        doc.save(fileName);

    } catch (error) {
        console.error('PDF generation error:', error);
        throw new Error('Failed to generate PDF: ' + error.message);
    }
}
// WebSocket/Socket.IO functions for real-time updates
function initializeWebSocket() {
    try {
        // Initialize Socket.IO connection
        socket = io(API_BASE, {
            transports: ['websocket', 'polling'],
            timeout: 20000,
            forceNew: true
        });

        // Connection event handlers
        socket.on('connect', () => {
            console.log('PhisGuard: Connected to real-time server');
            // Join dashboard room for user-specific updates
            if (userId) {
                socket.emit('join_dashboard', { user_id: userId });
            }
        });

        socket.on('disconnect', () => {
            console.log('PhisGuard: Disconnected from real-time server');
        });

        socket.on('connect_error', (error) => {
            console.error('PhisGuard: WebSocket connection error:', error);
        });

        // Real-time event handlers
        socket.on('high_risk_detected', (data) => {
            console.log('PhisGuard: High-risk detection received:', data);
            handleRealTimeDetection(data);
        });

        socket.on('dashboard_joined', (data) => {
            console.log('PhisGuard: Joined dashboard room:', data);
        });

        socket.on('connected', (data) => {
            console.log('PhisGuard: WebSocket connected:', data);
        });

    } catch (error) {
        console.error('PhisGuard: Failed to initialize WebSocket:', error);
    }
}

function handleRealTimeDetection(detectionData) {
    // Only update if dashboard is currently visible
    if (!dashboard.classList.contains('hidden')) {
        // Show a notification or update the dashboard
        showRealTimeNotification(detectionData);

        // Refresh dashboard data to show the new detection
        loadDashboardData();
    } else {
        // Store the detection for when dashboard is opened
        storePendingDetection(detectionData);
    }
}

function showRealTimeNotification(detectionData) {
    // Create a temporary notification in the dashboard
    const notification = document.createElement('div');
    notification.className = 'real-time-notification';
    notification.innerHTML = `
        <div class="notification-content">
            <strong>🚨 High-Risk URL Detected!</strong><br>
            <small>${detectionData.url}</small><br>
            <small>Risk Score: ${detectionData.risk_score}/100</small>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;

    // Add to dashboard
    dashboard.insertBefore(notification, dashboard.firstChild);

    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 10000);
}

function storePendingDetection(detectionData) {
    // Store pending detections in chrome storage
    chrome.storage.local.get(['pending_detections'], (result) => {
        const pending = result.pending_detections || [];
        pending.unshift(detectionData);

        // Keep only last 5 pending detections
        if (pending.length > 5) {
            pending.splice(5);
        }

        chrome.storage.local.set({ pending_detections: pending });
    });
}

// Load and display any pending detections when dashboard opens
function loadPendingDetections() {
    chrome.storage.local.get(['pending_detections'], (result) => {
        const pending = result.pending_detections || [];
        if (pending.length > 0) {
            // Show the most recent pending detection
            showRealTimeNotification(pending[0]);

            // Clear pending detections after showing
            chrome.storage.local.set({ pending_detections: [] });
        }
    });
}
