// PhisGuard Content Script
// Automatically scans links for security risks and adds visual indicators
// Blocks dangerous pages with warning overlay
// Includes Gmail email scanning functionality

// CSS is injected via manifest.json content_scripts

// Function to check a single link via background script
async function checkLink(url) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: 'checkUrl', data: { url } }, (response) => {
      resolve(response);
    });
  });
}

// Function to get warning settings from storage
async function getWarningSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['warningEnabled', 'warningSensitivity'], (result) => {
      resolve({
        enabled: result.warningEnabled !== false, // Default to true
        sensitivity: result.warningSensitivity || 'medium' // Default to medium
      });
    });
  });
}

// Function to check current page URL for warnings
async function checkCurrentPage() {
   console.log('PhisGuard: checkCurrentPage called for URL:', window.location.href);
   const currentUrl = window.location.href;

  console.log('PhisGuard: checkCurrentPage called for URL:', currentUrl);

  // Skip internal pages and safe protocols
  if (currentUrl.startsWith('chrome://') ||
      currentUrl.startsWith('chrome-extension://') ||
      currentUrl.startsWith('about:') ||
      currentUrl.startsWith('file://')) {
    console.log('PhisGuard: Skipping internal URL');
    return;
  }

  try {
    // Get user preferences
    const settings = await getWarningSettings();
    console.log('PhisGuard: Warning settings:', settings);

    // Skip if automatic scanning is disabled
    if (!settings.enabled) {
      console.log('PhisGuard: Automatic scanning disabled');
      return;
    }

    console.log('PhisGuard: Checking link via background script');
    const response = await checkLink(currentUrl);
    console.log('PhisGuard: Response from background:', response);

    if (response && response.success && response.data) {
      const riskData = response.data;
      console.log('PhisGuard: Risk data received:', riskData);

      // Check if page should show warning popup for high risk score
      if (riskData.risk_score > 70) {
        console.log('PhisGuard: High risk score detected, showing popup:', riskData.risk_score);
        showWarningPopup(riskData);
      }
      // Check if page should show warning based on sensitivity
      else if (shouldShowWarning(riskData, settings.sensitivity)) {
        console.log('PhisGuard: Showing warning banner');
        showWarningBanner(riskData);
      }
      // Check if page should be blocked (very high risk + multiple confirmations)
      else if (shouldBlockPage(riskData)) {
        console.log('PhisGuard: Showing blocking overlay');
        showBlockingOverlay(riskData);
      } else {
        console.log('PhisGuard: No warning needed, risk score:', riskData.risk_score);
      }
    } else {
      console.log('PhisGuard: No valid response from background');
    }
  } catch (error) {
    console.error('PhisGuard: Error checking current page', error);
  }
}

// Function to check if we're on Gmail
function isGmail() {
  return window.location.hostname === 'mail.google.com';
}

// Function to check email content via background script
async function checkEmailContent(subject, body) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({
      action: 'checkEmailText',
      data: { subject, body }
    }, (response) => {
      resolve(response);
    });
  });
}

// Function to extract email content from Gmail DOM
function extractEmailContent() {
  // Gmail selectors for email content (these may need updates as Gmail changes)
  const subjectSelectors = [
    'h2[data-thread-id] span', // Opened email subject
    '.ha h2 span', // Alternative subject selector
    '[data-thread-perm-id] h2 span' // Another variant
  ];

  const bodySelectors = [
    '.a3s.aiL', // Email body content
    '[data-message-id] .a3s', // Message body
    '.message-body', // Alternative body selector
    '.adn.ads' // Another body variant
  ];

  let subject = '';
  let body = '';

  // Extract subject
  for (const selector of subjectSelectors) {
    const element = document.querySelector(selector);
    if (element && element.textContent.trim()) {
      subject = element.textContent.trim();
      break;
    }
  }

  // Extract body
  for (const selector of bodySelectors) {
    const element = document.querySelector(selector);
    if (element && element.textContent.trim()) {
      body = element.textContent.trim();
      break;
    }
  }

  return { subject, body };
}

// Function to add email warning indicator in Gmail
function addEmailWarning(riskData, emailElement) {
  // Remove existing warnings
  const existingWarning = emailElement.querySelector('.phisguard-email-warning');
  if (existingWarning) existingWarning.remove();

  // Create warning element
  const warning = document.createElement('div');
  warning.className = 'phisguard-email-warning';

  // Clamp risk score to maximum of 100
  const rawRiskScore = riskData.risk_score || 0;
  const riskScore = Math.min(100, Math.round(rawRiskScore > 1 ? rawRiskScore : rawRiskScore * 100));
  const riskLevel = riskData.recommendation;

  let icon = '';
  let warningClass = '';

  if (riskLevel === 'danger') {
    icon = '🚨';
    warningClass = 'high-risk';
  } else if (riskLevel === 'caution') {
    icon = '⚠️';
    warningClass = 'medium-risk';
  } else {
    icon = '✅';
    warningClass = 'safe';
  }

  warning.classList.add(warningClass);
  warning.innerHTML = `
    <div class="phisguard-email-warning-content">
      <span class="phisguard-email-warning-icon">${icon}</span>
      <span class="phisguard-email-warning-text">
        Phishing Risk: ${riskScore}/100
      </span>
      <button class="phisguard-email-details-btn" title="View details">ℹ️</button>
    </div>
  `;

  // Add click handler for details
  const detailsBtn = warning.querySelector('.phisguard-email-details-btn');
  detailsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    showEmailWarningDetails(riskData);
  });

  // Insert warning at the top of the email
  emailElement.insertBefore(warning, emailElement.firstChild);
}

// Function to show detailed email warning
function showEmailWarningDetails(riskData) {
  // Clamp risk score to maximum of 100
  const rawRiskScore = riskData.risk_score || 0;
  const riskScore = Math.min(100, Math.round(rawRiskScore > 1 ? rawRiskScore : rawRiskScore * 100));

  const details = `
Phishing Analysis Results:

Risk Score: ${riskScore}/100
Risk Level: ${riskData.recommendation?.toUpperCase() || 'UNKNOWN'}

Analysis:
${riskData.analysis || 'No additional analysis available'}

Recommendations:
${riskData.recommendation === 'danger' ?
  '• Do not click any links in this email\n• Do not provide any personal information\n• Delete this email immediately\n• Report as phishing if possible' :
  riskData.recommendation === 'caution' ?
  '• Verify the sender independently\n• Be cautious with any links or attachments\n• Check for suspicious content' :
  '• This email appears safe\n• Continue with normal caution'
}
  `;

  alert(details);
}

// Function to determine if page should show warning based on sensitivity
function shouldShowWarning(riskData, sensitivity) {
  const riskScore = riskData.risk_score || 0;
  // Map API recommendation to risk level
  const recommendation = riskData.recommendation || 'safe';
  let riskLevel = 'low';
  if (recommendation === 'caution') riskLevel = 'medium';
  else if (recommendation === 'danger') riskLevel = 'high';

  switch (sensitivity) {
    case 'high':
      return riskScore >= 70 || riskLevel === 'high';
    case 'medium':
      return riskScore >= 40 || riskLevel === 'medium' || riskLevel === 'high';
    case 'low':
      return riskScore >= 20 || riskLevel === 'low' || riskLevel === 'medium' || riskLevel === 'high';
    default:
      return riskScore >= 40 || riskLevel === 'medium' || riskLevel === 'high';
  }
}

// Function to determine if page should be blocked
function shouldBlockPage(riskData) {
  // Block if high risk (danger recommendation) and multiple detection methods agree
  const recommendation = riskData.recommendation || 'safe';
  if (recommendation !== 'danger') return false;

  const details = riskData.details || [];
  let detectionCount = 0;

  // Count different detection methods
  if (details.some(d => d.includes('VIRUSTOTAL'))) detectionCount++;
  if (details.some(d => d.includes('ML Model'))) detectionCount++;
  if (details.some(d => d.includes('SSL') || d.includes('HTTPS'))) detectionCount++;
  if (details.some(d => d.includes('suspicious') || d.includes('phishing'))) detectionCount++;

  // Require at least 2 detection methods to agree
  return detectionCount >= 2;
}

// Function to show blocking overlay
function showBlockingOverlay(riskData) {
  // Prevent scrolling and interaction
  document.body.style.overflow = 'hidden';

  // Create overlay
  const overlay = document.createElement('div');
  overlay.id = 'phisguard-block-overlay';
  overlay.innerHTML = `
    <div class="phisguard-block-content">
      <div class="phisguard-block-header">
        <div class="phisguard-block-icon">🚨</div>
        <h1>DANGEROUS WEBSITE DETECTED</h1>
        <p>This website has been flagged as potentially harmful</p>
      </div>

      <div class="phisguard-block-stats">
        <div class="phisguard-stat-item">
          <span class="stat-label">Risk Score:</span>
          <span class="stat-value high-risk">${Math.min(100, Math.round((riskData.risk_score || 0) > 1 ? (riskData.risk_score || 0) : (riskData.risk_score || 0) * 100))}/100</span>
        </div>
        <div class="phisguard-stat-item">
          <span class="stat-label">Risk Level:</span>
          <span class="stat-value high-risk">${riskData.risk_level?.toUpperCase() || 'UNKNOWN'}</span>
        </div>
        <div class="phisguard-stat-item">
          <span class="stat-label">Detection Methods:</span>
          <span class="stat-value">${countDetections(riskData.details || [])}</span>
        </div>
      </div>

      <div class="phisguard-block-details">
        <h3>Security Analysis:</h3>
        <ul>
          ${(riskData.details || []).map(detail => `<li>${detail}</li>`).join('')}
        </ul>
      </div>

      <div class="phisguard-block-actions">
        <button class="phisguard-btn phisguard-btn-secondary" id="go-back-btn">
          ← Go Back to Safety
        </button>
        <button class="phisguard-btn phisguard-btn-danger" id="proceed-anyway-btn">
          ⚠️ Proceed Anyway
        </button>
      </div>

      <div class="phisguard-block-footer">
        <p>Protected by <strong>PhisGuard</strong> - Advanced Phishing Detection</p>
      </div>
    </div>
  `;

  // Add overlay styles
  const style = document.createElement('style');
  style.textContent = `
    #phisguard-block-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.9);
      z-index: 999999;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .phisguard-block-content {
      background: white;
      border-radius: 12px;
      padding: 30px;
      max-width: 500px;
      width: 90%;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
      text-align: center;
      animation: phisguard-fade-in 0.3s ease-out;
    }

    @keyframes phisguard-fade-in {
      from { opacity: 0; transform: scale(0.9); }
      to { opacity: 1; transform: scale(1); }
    }

    .phisguard-block-header {
      margin-bottom: 25px;
    }

    .phisguard-block-icon {
      font-size: 48px;
      margin-bottom: 10px;
    }

    .phisguard-block-header h1 {
      color: #dc3545;
      margin: 10px 0;
      font-size: 24px;
      font-weight: bold;
    }

    .phisguard-block-header p {
      color: #666;
      margin: 0;
      font-size: 16px;
    }

    .phisguard-block-stats {
      display: grid;
      grid-template-columns: 1fr;
      gap: 15px;
      margin: 25px 0;
      padding: 20px;
      background: #f8f9fa;
      border-radius: 8px;
    }

    .phisguard-stat-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .stat-label {
      font-weight: 600;
      color: #333;
    }

    .stat-value {
      font-weight: bold;
      font-size: 18px;
    }

    .stat-value.high-risk {
      color: #dc3545;
    }

    .phisguard-block-details {
      text-align: left;
      margin: 25px 0;
      max-height: 200px;
      overflow-y: auto;
    }

    .phisguard-block-details h3 {
      margin-top: 0;
      color: #333;
      font-size: 18px;
    }

    .phisguard-block-details ul {
      margin: 10px 0 0 0;
      padding-left: 20px;
    }

    .phisguard-block-details li {
      margin: 5px 0;
      color: #555;
      line-height: 1.4;
    }

    .phisguard-block-actions {
      display: flex;
      gap: 15px;
      justify-content: center;
      margin: 30px 0 20px 0;
    }

    .phisguard-btn {
      padding: 12px 24px;
      border: none;
      border-radius: 6px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .phisguard-btn-secondary {
      background: #6c757d;
      color: white;
    }

    .phisguard-btn-secondary:hover {
      background: #5a6268;
      transform: translateY(-1px);
    }

    .phisguard-btn-danger {
      background: #dc3545;
      color: white;
    }

    .phisguard-btn-danger:hover {
      background: #c82333;
      transform: translateY(-1px);
    }

    .phisguard-block-footer {
      margin-top: 20px;
      padding-top: 20px;
      border-top: 1px solid #eee;
      color: #666;
      font-size: 14px;
    }

    .phisguard-block-footer strong {
      color: #007bff;
    }

    @media (max-width: 600px) {
      .phisguard-block-content {
        padding: 20px;
        margin: 20px;
      }

      .phisguard-block-actions {
        flex-direction: column;
      }

      .phisguard-btn {
        width: 100%;
      }
    }
  `;


  document.head.appendChild(style);
  document.body.appendChild(overlay);

  // Add event listeners programmatically
  const goBackBtn = overlay.querySelector('#go-back-btn');
  const proceedBtn = overlay.querySelector('#proceed-anyway-btn');

  if (goBackBtn) {
    goBackBtn.addEventListener('click', function() {
      try {
        window.history.back();
      } catch (error) {
        console.error('Error going back:', error);
        // Fallback: navigate to chrome://newtab
        window.location.href = 'chrome://newtab';
      }
    });
  }

  if (proceedBtn) {
    proceedBtn.addEventListener('click', function() {
      try {
        overlay.remove();
        style.remove();
        document.body.style.overflow = '';
      } catch (error) {
        console.error('Error proceeding anyway:', error);
      }
    });
  }
}

// Function to show warning popup for high-risk sites
function showWarningPopup(riskData) {
 // Remove existing popup if present
 const existingPopup = document.getElementById('phisguard-warning-popup');
 if (existingPopup) existingPopup.remove();

 // Clamp risk score to maximum of 100 and ensure it's properly formatted
 const rawRiskScore = riskData.risk_score || 0;
 const riskScore = Math.min(100, Math.round(rawRiskScore > 1 ? rawRiskScore : rawRiskScore * 100));
 const riskLevel = riskData.recommendation || 'caution';

 const popup = document.createElement('div');
 popup.id = 'phisguard-warning-popup';
 popup.innerHTML = `
   <div class="phisguard-popup-overlay">
     <div class="phisguard-popup-content">
       <div class="phisguard-popup-header">
         <div class="phisguard-popup-icon">🚨</div>
         <h1>Security Warning</h1>
         <p>This website has been detected as potentially dangerous</p>
       </div>

       <div class="phisguard-popup-stats">
         <div class="phisguard-stat-item">
           <span class="stat-label">Risk Score:</span>
           <span class="stat-value high-risk">${riskScore}/100</span>
         </div>
         <div class="phisguard-stat-item">
           <span class="stat-label">Risk Level:</span>
           <span class="stat-value high-risk">${riskLevel.toUpperCase()}</span>
         </div>
       </div>

       <div class="phisguard-popup-details">
         <h3>Why is this site considered dangerous?</h3>
         <ul>
           ${(riskData.details || []).map(detail => `<li>${detail}</li>`).join('')}
         </ul>
       </div>

       <div class="phisguard-popup-actions">
         <button class="phisguard-btn phisguard-btn-secondary" id="dismiss-warning-btn">
           I Understand - Continue
         </button>
         <button class="phisguard-btn phisguard-btn-danger" id="leave-site-btn">
           🚪 Leave This Site
         </button>
       </div>

       <div class="phisguard-popup-footer">
         <p>Protected by <strong>PhisGuard</strong> - Advanced Phishing Detection</p>
       </div>
     </div>
   </div>
 `;

 // Add popup styles
 const style = document.createElement('style');
 style.textContent = `
   #phisguard-warning-popup {
     position: fixed;
     top: 0;
     left: 0;
     width: 100%;
     height: 100%;
     z-index: 999998;
     display: flex;
     align-items: center;
     justify-content: center;
     font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
   }

   .phisguard-popup-overlay {
     position: absolute;
     top: 0;
     left: 0;
     width: 100%;
     height: 100%;
     background: rgba(0, 0, 0, 0.7);
     display: flex;
     align-items: center;
     justify-content: center;
     padding: 20px;
     box-sizing: border-box;
   }

   .phisguard-popup-content {
     background: white;
     border-radius: 12px;
     padding: 30px;
     max-width: 500px;
     width: 100%;
     box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
     text-align: center;
     animation: phisguard-popup-fade-in 0.3s ease-out;
     position: relative;
   }

   @keyframes phisguard-popup-fade-in {
     from { opacity: 0; transform: scale(0.9); }
     to { opacity: 1; transform: scale(1); }
   }

   .phisguard-popup-header {
     margin-bottom: 25px;
   }

   .phisguard-popup-icon {
     font-size: 48px;
     margin-bottom: 10px;
     color: #dc3545;
   }

   .phisguard-popup-header h1 {
     color: #dc3545;
     margin: 10px 0;
     font-size: 24px;
     font-weight: bold;
   }

   .phisguard-popup-header p {
     color: #666;
     margin: 0;
     font-size: 16px;
   }

   .phisguard-popup-stats {
     display: grid;
     grid-template-columns: 1fr;
     gap: 15px;
     margin: 25px 0;
     padding: 20px;
     background: #f8f9fa;
     border-radius: 8px;
   }

   .phisguard-stat-item {
     display: flex;
     justify-content: space-between;
     align-items: center;
   }

   .stat-label {
     font-weight: 600;
     color: #333;
   }

   .stat-value {
     font-weight: bold;
     font-size: 18px;
   }

   .stat-value.high-risk {
     color: #dc3545;
   }

   .phisguard-popup-details {
     text-align: left;
     margin: 25px 0;
     max-height: 200px;
     overflow-y: auto;
   }

   .phisguard-popup-details h3 {
     margin-top: 0;
     color: #333;
     font-size: 18px;
   }

   .phisguard-popup-details ul {
     margin: 10px 0 0 0;
     padding-left: 20px;
   }

   .phisguard-popup-details li {
     margin: 5px 0;
     color: #555;
     line-height: 1.4;
   }

   .phisguard-popup-actions {
     display: flex;
     gap: 15px;
     justify-content: center;
     margin: 30px 0 20px 0;
   }

   .phisguard-btn {
     padding: 12px 24px;
     border: none;
     border-radius: 6px;
     font-size: 16px;
     font-weight: 600;
     cursor: pointer;
     transition: all 0.2s ease;
   }

   .phisguard-btn-secondary {
     background: #6c757d;
     color: white;
   }

   .phisguard-btn-secondary:hover {
     background: #5a6268;
     transform: translateY(-1px);
   }

   .phisguard-btn-danger {
     background: #dc3545;
     color: white;
   }

   .phisguard-btn-danger:hover {
     background: #c82333;
     transform: translateY(-1px);
   }

   .phisguard-popup-footer {
     margin-top: 20px;
     padding-top: 20px;
     border-top: 1px solid #eee;
     color: #666;
     font-size: 14px;
   }

   .phisguard-popup-footer strong {
     color: #007bff;
   }

   @media (max-width: 600px) {
     .phisguard-popup-content {
       padding: 20px;
       margin: 20px;
     }

     .phisguard-popup-actions {
       flex-direction: column;
     }

     .phisguard-btn {
       width: 100%;
     }
   }
 `;


 document.head.appendChild(style);
 document.body.appendChild(popup);

 // Add event listeners programmatically
 const dismissBtn = popup.querySelector('#dismiss-warning-btn');
 const leaveBtn = popup.querySelector('#leave-site-btn');

 if (dismissBtn) {
   dismissBtn.addEventListener('click', function() {
     try {
       if (popup && popup.parentNode) {
         popup.remove();
       }
       if (style && style.parentNode) {
         style.remove();
       }
     } catch (error) {
       console.error('Error dismissing warning popup:', error);
     }
   });
 }

 if (leaveBtn) {
   leaveBtn.addEventListener('click', function() {
     try {
       if (confirm('Are you sure you want to leave this site? This will take you to a safe page.')) {
         // Navigate to chrome.com (safe and reliable)
         window.location.href = 'https://chrome.com';
       }
     } catch (error) {
       console.error('Error leaving site from popup:', error);
       // Emergency fallback
       try {
         window.location.href = 'about:blank';
       } catch (fallbackError) {
         console.error('Even fallback failed:', fallbackError);
       }
     }
   });
 }
}

// Function to show warning banner at top of page
function showWarningBanner(riskData) {
  // Remove existing warning if present
  const existingWarning = document.getElementById('phisguard-warning-banner');
  if (existingWarning) existingWarning.remove();

  // Clamp risk score to maximum of 100
  const rawRiskScore = riskData.risk_score || 0;
  const riskScore = Math.min(100, Math.round(rawRiskScore > 1 ? rawRiskScore : rawRiskScore * 100));
  const riskLevel = riskData.recommendation || 'caution';

  let icon = '';
  let bgColor = '';
  let borderColor = '';
  let textColor = '';
  let severityText = '';

  if (riskLevel === 'danger') {
    icon = '🚨';
    bgColor = '#f8d7da';
    borderColor = '#f5c6cb';
    textColor = '#721c24';
    severityText = 'HIGH RISK';
  } else if (riskLevel === 'caution') {
    icon = '⚠️';
    bgColor = '#fff3cd';
    borderColor = '#ffeaa7';
    textColor = '#856404';
    severityText = 'MEDIUM RISK';
  } else {
    icon = 'ℹ️';
    bgColor = '#d1ecf1';
    borderColor = '#bee5eb';
    textColor = '#0c5460';
    severityText = 'LOW RISK';
  }

  // Get key security indicators
  const indicators = getSecurityIndicators(riskData.details || []);

  const banner = document.createElement('div');
  banner.id = 'phisguard-warning-banner';
  banner.className = `${riskLevel}-risk`; // Add risk level class for styling
  banner.innerHTML = `
    <div class="phisguard-warning-content">
      <div class="phisguard-warning-header">
        <div class="phisguard-warning-icon">${icon}</div>
        <div class="phisguard-warning-title">
          <strong>PhisGuard Security Alert</strong>
          <div class="phisguard-severity">${severityText}</div>
        </div>
      </div>
      <div class="phisguard-warning-body">
        <div class="phisguard-risk-summary">
          <span class="risk-score">Risk Score: ${riskScore}/100</span>
          <span class="risk-indicators">${indicators}</span>
        </div>
        <div class="phisguard-warning-message">
          ${getWarningMessage(riskLevel)}
        </div>
        <div class="phisguard-key-threats">
          ${getKeyThreats(riskData.details || [])}
        </div>
      </div>
      <div class="phisguard-warning-actions">
        <button class="phisguard-btn phisguard-btn-info" id="view-details-btn" title="View comprehensive security analysis">
          🔍 Details
        </button>
        <button class="phisguard-btn phisguard-btn-secondary" id="dismiss-warning-btn" title="Hide this warning">
          Dismiss
        </button>
        <button class="phisguard-btn phisguard-btn-danger" id="leave-site-btn" title="Leave this website immediately">
          🚪 Leave Site
        </button>
      </div>
      <button class="phisguard-warning-close" onclick="dismissWarning()" title="Close warning">×</button>
    </div>
  `;

  // Add styles
  const style = document.createElement('style');
  style.textContent = `
    #phisguard-warning-banner {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      background: ${bgColor};
      border-bottom: 2px solid ${borderColor};
      color: ${textColor};
      padding: 12px 20px;
      z-index: 10000;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      animation: phisguard-slide-down 0.3s ease-out;
    }

    @keyframes phisguard-slide-down {
      from { transform: translateY(-100%); }
      to { transform: translateY(0); }
    }

    .phisguard-warning-content {
      display: flex;
      align-items: center;
      gap: 12px;
      max-width: 1200px;
      margin: 0 auto;
      position: relative;
    }

    .phisguard-warning-icon {
      font-size: 20px;
      flex-shrink: 0;
    }

    .phisguard-warning-text {
      flex: 1;
      font-weight: 500;
    }

    .phisguard-warning-details {
      flex: 1;
      font-size: 13px;
      opacity: 0.9;
    }

    .phisguard-warning-actions {
      display: flex;
      gap: 8px;
      flex-shrink: 0;
    }

    .phisguard-btn {
      padding: 6px 12px;
      border: 1px solid ${borderColor};
      border-radius: 4px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      background: transparent;
    }

    .phisguard-btn:hover {
      opacity: 0.8;
      transform: translateY(-1px);
    }

    .phisguard-btn-primary {
      background: ${textColor};
      color: white;
      border-color: ${textColor};
    }

    .phisguard-btn-danger {
      background: #dc3545;
      color: white;
      border-color: #dc3545;
    }

    .phisguard-btn-danger:hover {
      background: #c82333;
      border-color: #c82333;
    }

    .phisguard-warning-close {
      position: absolute;
      top: -8px;
      right: -8px;
      background: ${bgColor};
      border: 1px solid ${borderColor};
      border-radius: 50%;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 16px;
      color: ${textColor};
      transition: all 0.2s ease;
    }

    .phisguard-warning-close:hover {
      background: ${borderColor};
    }

    @media (max-width: 768px) {
      .phisguard-warning-content {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
      }

      .phisguard-warning-actions {
        width: 100%;
        justify-content: flex-end;
      }

      .phisguard-btn {
        flex: 1;
        text-align: center;
      }
    }
  `;


  document.head.appendChild(style);
  document.body.insertBefore(banner, document.body.firstChild);

  // Add event listeners programmatically
  const viewDetailsBtn = banner.querySelector('#view-details-btn');
  const dismissBtn = banner.querySelector('#dismiss-warning-btn');
  const leaveBtn = banner.querySelector('#leave-site-btn');

  if (viewDetailsBtn) {
    viewDetailsBtn.addEventListener('click', function() {
      const detailsList = riskData.details || [];
      const formattedDetails = detailsList.map(detail => `• ${detail}`).join('\n');

      const details = `
Security Analysis Results:

Risk Score: ${riskScore}/100
Risk Level: ${riskLevel.toUpperCase()}

Analysis Details:
${formattedDetails || 'No analysis details available'}

Recommendations:
${getDetailedRecommendations(riskLevel)}
      `.trim();

      alert(details);
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener('click', function() {
      banner.remove();
      style.remove();
      document.body.style.paddingTop = '';
    });
  }

  if (leaveBtn) {
    leaveBtn.addEventListener('click', function() {
      if (confirm('Are you sure you want to leave this page?')) {
        window.history.back();
      }
    });
  }

  // Adjust body padding to account for fixed banner
  document.body.style.paddingTop = '60px';
}

// Helper function to get security indicators
function getSecurityIndicators(details) {
  const indicators = [];
  if (details.some(d => d.includes('VIRUSTOTAL'))) indicators.push('🔍 AV Scan');
  if (details.some(d => d.includes('SSL') || d.includes('HTTPS'))) indicators.push('🔒 SSL Check');
  if (details.some(d => d.includes('ML Model'))) indicators.push('🤖 AI Analysis');
  if (details.some(d => d.includes('Google Safe Browsing'))) indicators.push('🌐 Safe Browsing');
  return indicators.join(' • ');
}

// Helper function to get key threats
function getKeyThreats(details) {
  const threats = [];
  if (details.some(d => d.includes('malicious'))) threats.push('• Detected as malicious by antivirus engines');
  if (details.some(d => d.includes('phishing'))) threats.push('• Potential phishing indicators found');
  if (details.some(d => d.includes('Invalid SSL'))) threats.push('• SSL certificate issues detected');
  if (details.some(d => d.includes('suspicious'))) threats.push('• Suspicious URL patterns identified');

  if (threats.length === 0) {
    threats.push('• General security concerns identified');
  }

  return threats.slice(0, 2).join('\n'); // Limit to 2 threats
}

// Helper function to get warning message
function getWarningMessage(riskLevel) {
  switch (riskLevel) {
    case 'danger':
      return '🚨 CRITICAL: This website poses significant security risks. Do not enter personal information or click suspicious links.';
    case 'caution':
      return '⚠️ CAUTION: This website has security concerns. Verify the site\'s legitimacy before proceeding.';
    default:
      return 'ℹ️ NOTICE: This website has minor security considerations. Continue with normal caution.';
  }
}

// Helper function to get detailed recommendations
function getDetailedRecommendations(riskLevel) {
  switch (riskLevel) {
    case 'danger':
      return '• Do not enter any personal information\n• Do not click on any links or download files\n• Consider leaving this page immediately\n• Report suspicious activity if possible';
    case 'caution':
      return '• Verify the website URL carefully\n• Be cautious with any forms or downloads\n• Check for HTTPS security\n• Consider alternative trusted sources';
    default:
      return '• Continue with normal caution\n• Verify information from multiple sources if possible';
  }
}

// Helper function to count detections
function countDetections(details) {
  let count = 0;
  if (details.some(d => d.includes('VIRUSTOTAL'))) count++;
  if (details.some(d => d.includes('ML Model'))) count++;
  if (details.some(d => d.includes('SSL') || d.includes('HTTPS'))) count++;
  if (details.some(d => d.includes('suspicious') || d.includes('phishing'))) count++;
  return count;
}

// Function to add visual indicators and tooltips to a link
function addIndicator(link, riskData) {
  // Remove existing indicators
  const existingIndicator = link.parentNode.querySelector('.phisguard-indicator');
  if (existingIndicator) existingIndicator.remove();

  const existingTooltip = link.parentNode.querySelector('.phisguard-tooltip');
  if (existingTooltip) existingTooltip.remove();

  const existingAction = link.parentNode.querySelector('.phisguard-quick-action');
  if (existingAction) existingAction.remove();

  // Create indicator element
  const indicator = document.createElement('span');
  indicator.className = 'phisguard-indicator';

  // Add link class for highlighting
  link.classList.add('phisguard-link');

  // Determine risk level and styling
  let icon = '';
  let tooltipText = '';
  let riskClass = '';

  if (riskData.risk_level === 'high') {
    riskClass = 'high-risk';
    icon = '⚠️';
    tooltipText = `High Risk: ${riskData.details || 'This link appears suspicious'}`;
  } else if (riskData.risk_level === 'medium') {
    riskClass = 'medium-risk';
    icon = '⚡';
    tooltipText = `Medium Risk: ${riskData.details || 'This link may be risky'}`;
  } else {
    riskClass = 'safe';
    icon = '✅';
    tooltipText = 'Safe: This link appears secure';
  }

  indicator.classList.add(riskClass);
  indicator.innerHTML = icon;
  indicator.title = tooltipText;

  link.classList.add(riskClass);

  // Create tooltip element
  const tooltip = document.createElement('div');
  tooltip.className = 'phisguard-tooltip';
  tooltip.textContent = tooltipText;

  // Show tooltip on hover
  indicator.addEventListener('mouseenter', (e) => {
    tooltip.style.display = 'block';
    tooltip.style.left = `${e.pageX + 10}px`;
    tooltip.style.top = `${e.pageY + 10}px`;
    document.body.appendChild(tooltip);
  });

  indicator.addEventListener('mouseleave', () => {
    tooltip.style.display = 'none';
    if (tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
  });

  // Create quick action button
  const actionButton = document.createElement('button');
  actionButton.className = 'phisguard-quick-action';
  actionButton.textContent = 'Details';

  // Add loading state management
  let isLoading = false;

  actionButton.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (isLoading) return; // Prevent multiple clicks

    isLoading = true;
    const originalText = actionButton.textContent;

    // Show enhanced loading state
    actionButton.textContent = '🔍 Analyzing...';
    actionButton.disabled = true;
    actionButton.style.background = '#6c757d';

    // Add timeout for the request
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('Request timeout')), 15000); // 15 second timeout
    });

    try {
      // Race between the API call and timeout
      const response = await Promise.race([
        new Promise((resolve) => {
          chrome.runtime.sendMessage({
            action: 'comprehensiveCheck',
            data: { url: link.href }
          }, resolve);
        }),
        timeoutPromise
      ]);

      if (response && response.success && response.data) {
        showSecurityDetailsModal(link.href, response.data);
      } else {
        const errorMsg = response?.error || 'Failed to fetch security details. The service may be temporarily unavailable or rate limited.';
        showErrorModal(errorMsg + ' Please try again later.');
      }
    } catch (error) {
      console.error('PhisGuard: Details request failed', error);
      showErrorModal('Request timed out. The security analysis service is taking too long to respond. Please try again later.');
    } finally {
      // Reset button state
      isLoading = false;
      actionButton.textContent = originalText;
      actionButton.disabled = false;
      actionButton.style.background = '';
    }
  });

  // Insert elements before the link
  link.parentNode.insertBefore(indicator, link);
  link.parentNode.insertBefore(actionButton, link.nextSibling);
}

// Function to filter links that should be checked
function shouldCheckLink(url) {
  if (!url) return false;

  // Skip non-HTTP protocols
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return false;
  }

  // Skip internal Chrome pages and extensions
  if (url.startsWith('chrome://') || url.startsWith('chrome-extension://') ||
      url.startsWith('about:') || url.startsWith('file://')) {
    return false;
  }

  // Skip very short URLs (likely fragments or relative paths)
  if (url.length < 10) {
    return false;
  }

  // Skip URLs without proper domain structure
  if (!url.includes('.') || url.split('.').length < 2) {
    return false;
  }

  // Skip obvious safe internal links (relative paths, anchors)
  if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) {
    return false;
  }

  // Skip same-domain links (likely internal navigation)
  try {
    const linkDomain = new URL(url).hostname;
    const currentDomain = window.location.hostname;
    if (linkDomain === currentDomain) {
      return false;
    }
  } catch (e) {
    // If URL parsing fails, skip it
    return false;
  }

  return true;
}

// Function to process a batch of links
async function processLinks(links) {
  const validLinks = Array.from(links).filter(link => shouldCheckLink(link.href));

  console.log(`PhisGuard: Processing ${validLinks.length} external links out of ${links.length} total links`);

  if (validLinks.length === 0) return;

  // Process links in smaller batches to avoid overwhelming
  const batchSize = 3; // Reduced batch size
  for (let i = 0; i < validLinks.length; i += batchSize) {
    const batch = validLinks.slice(i, i + batchSize);
    await Promise.all(batch.map(async (link) => {
      try {
        const response = await checkLink(link.href);
        if (response && response.success) {
          addIndicator(link, response.data);
        }
      } catch (error) {
        console.error('PhisGuard: Error checking link', link.href, error);
      }
    }));
    // Small delay between batches
    await new Promise(resolve => setTimeout(resolve, 200)); // Increased delay
  }
}

// Function to scan Gmail emails
async function scanGmailEmails() {
  if (!isGmail()) return;

  try {
    const { subject, body } = extractEmailContent();

    if (subject || body) {
      console.log('PhisGuard: Scanning Gmail email - Subject:', subject.substring(0, 50) + '...');

      const response = await checkEmailContent(subject, body);
      if (response && response.success && response.data) {
        const riskData = response.data;

        // Find the email container to add warning
        const emailContainer = document.querySelector('[data-message-id]') ||
                              document.querySelector('.adn.ads') ||
                              document.querySelector('.message-body') ||
                              document.body; // Fallback

        if (emailContainer) {
          addEmailWarning(riskData, emailContainer);
        }
      }
    }
  } catch (error) {
    console.error('PhisGuard: Error scanning Gmail email', error);
  }
}

// Initial scan on page load
document.addEventListener('DOMContentLoaded', async () => {
  // Check current page for blocking
  await checkCurrentPage();

  // Scan links for indicators
  const links = document.querySelectorAll('a');
  processLinks(links);

  // Scan Gmail emails if on Gmail
  if (isGmail()) {
    // Initial scan
    setTimeout(scanGmailEmails, 2000); // Wait for Gmail to load
  }
});

// Also check when page is fully loaded (for better reliability)
window.addEventListener('load', async () => {
  console.log('PhisGuard: Page fully loaded, re-checking current page');
  // Re-check current page when fully loaded
  await checkCurrentPage();
});

// Handle dynamic content with MutationObserver
const observer = new MutationObserver((mutations) => {
  const newLinks = [];
  let gmailContentChanged = false;

  mutations.forEach((mutation) => {
    mutation.addedNodes.forEach((node) => {
      if (node.nodeType === Node.ELEMENT_NODE) {
        if (node.tagName === 'A') {
          newLinks.push(node);
        } else {
          const links = node.querySelectorAll ? node.querySelectorAll('a') : [];
          newLinks.push(...links);
        }

        // Check if Gmail email content changed
        if (isGmail() && (
          node.matches?.('[data-message-id]') ||
          node.querySelector?.('[data-message-id]') ||
          node.matches?.('.a3s.aiL') ||
          node.querySelector?.('.a3s.aiL')
        )) {
          gmailContentChanged = true;
        }
      }
    });
  });

  if (newLinks.length > 0) {
    // Debounce processing of new links
    clearTimeout(window.phisguardDebounce);
    window.phisguardDebounce = setTimeout(() => {
      processLinks(newLinks);
    }, 500);
  }

  // Handle Gmail email content changes
  if (gmailContentChanged) {
    clearTimeout(window.phisguardGmailDebounce);
    window.phisguardGmailDebounce = setTimeout(() => {
      scanGmailEmails();
    }, 1000); // Wait for content to fully load
  }
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

// Function to show comprehensive security details modal
function showSecurityDetailsModal(url, data) {
  // Remove existing modal if present
  const existingModal = document.getElementById('phisguard-details-modal');
  if (existingModal) existingModal.remove();

  const riskScore = Math.round(data.assessment?.overall_score || 0);
  const riskLevel = data.assessment?.risk_level || 'unknown';
  const recommendation = data.assessment?.recommendation || 'unknown';

  // Determine styling based on risk
  let headerClass = 'safe-header';
  let icon = '✅';
  if (recommendation === 'danger') {
    headerClass = 'danger-header';
    icon = '🚨';
  } else if (recommendation === 'caution') {
    headerClass = 'caution-header';
    icon = '⚠️';
  }

  const modal = document.createElement('div');
  modal.id = 'phisguard-details-modal';
  modal.innerHTML = `
    <div class="phisguard-modal-overlay">
      <div class="phisguard-modal-content">
        <div class="phisguard-modal-header ${headerClass}">
          <div class="phisguard-modal-title">
            <span class="phisguard-modal-icon">${icon}</span>
            <h2>Security Analysis Report</h2>
          </div>
          <button class="phisguard-modal-close" onclick="closeSecurityModal()">×</button>
        </div>

        <div class="phisguard-modal-body">
          <div class="phisguard-url-section">
            <h3>Analyzed URL</h3>
            <div class="phisguard-url-display">${url}</div>
          </div>

          <div class="phisguard-risk-summary">
            <div class="phisguard-risk-score">
              <h3>Risk Assessment</h3>
              <div class="risk-score-display">
                <span class="score-number">${riskScore}</span>
                <span class="score-label">/100</span>
              </div>
              <div class="risk-level">${riskLevel.toUpperCase()}</div>
              <div class="risk-recommendation">${recommendation.toUpperCase()}</div>
            </div>
          </div>

          <div class="phisguard-analysis-sections">
            ${renderAnalysisSection('URL Analysis', data.individual_checks?.url_check)}
            ${renderAnalysisSection('SSL Certificate', data.individual_checks?.ssl_check)}
            ${renderAnalysisSection('Link Expansion', data.individual_checks?.link_expansion)}
            ${renderAnalysisSection('Breach Check', data.individual_checks?.breach_check)}
            ${renderAnalysisSection('Email Analysis', data.individual_checks?.email_text_check)}
          </div>

          <div class="phisguard-recommendations">
            <h3>Security Recommendations</h3>
            <div class="recommendations-content">
              ${getSecurityRecommendations(recommendation)}
            </div>
          </div>
        </div>

      <div class="phisguard-modal-footer">
        <button class="phisguard-btn phisguard-btn-secondary" onclick="closeSecurityModal()">Close</button>
      </div>
      </div>
    </div>
  `;

  // Add modal styles
  const style = document.createElement('style');
  style.textContent = `
    #phisguard-details-modal {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 10001;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .phisguard-modal-overlay {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      box-sizing: border-box;
    }

    .phisguard-modal-content {
      background: white;
      border-radius: 12px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
      max-width: 800px;
      width: 100%;
      max-height: 90vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      animation: phisguard-modal-fade-in 0.3s ease-out;
    }

    @keyframes phisguard-modal-fade-in {
      from { opacity: 0; transform: scale(0.9); }
      to { opacity: 1; transform: scale(1); }
    }

    .phisguard-modal-header {
      padding: 20px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #dee2e6;
    }

    .phisguard-modal-header.danger-header {
      background: linear-gradient(135deg, #f8d7da, #f5c6cb);
      color: #721c24;
    }

    .phisguard-modal-header.caution-header {
      background: linear-gradient(135deg, #fff3cd, #ffeaa7);
      color: #856404;
    }

    .phisguard-modal-header.safe-header {
      background: linear-gradient(135deg, #d1ecf1, #bee5eb);
      color: #0c5460;
    }

    .phisguard-modal-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .phisguard-modal-icon {
      font-size: 24px;
    }

    .phisguard-modal-title h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }

    .phisguard-modal-close {
      background: none;
      border: none;
      font-size: 28px;
      cursor: pointer;
      color: inherit;
      padding: 0;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: background-color 0.2s ease;
    }

    .phisguard-modal-close:hover {
      background: rgba(0, 0, 0, 0.1);
    }

    .phisguard-modal-body {
      padding: 24px;
      overflow-y: auto;
      flex: 1;
    }

    .phisguard-url-section {
      margin-bottom: 24px;
    }

    .phisguard-url-section h3 {
      margin: 0 0 8px 0;
      font-size: 16px;
      color: #495057;
    }

    .phisguard-url-display {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      padding: 12px;
      font-family: monospace;
      font-size: 14px;
      word-break: break-all;
      color: #495057;
    }

    .phisguard-risk-summary {
      margin-bottom: 24px;
    }

    .phisguard-risk-score {
      text-align: center;
      padding: 20px;
      background: #f8f9fa;
      border-radius: 8px;
    }

    .phisguard-risk-score h3 {
      margin: 0 0 16px 0;
      color: #495057;
    }

    .risk-score-display {
      display: flex;
      align-items: baseline;
      justify-content: center;
      gap: 4px;
      margin-bottom: 8px;
    }

    .score-number {
      font-size: 48px;
      font-weight: bold;
      color: #dc3545;
    }

    .score-label {
      font-size: 24px;
      color: #6c757d;
    }

    .risk-level {
      font-size: 18px;
      font-weight: 600;
      color: #495057;
      margin-bottom: 4px;
    }

    .risk-recommendation {
      font-size: 14px;
      color: #6c757d;
      text-transform: uppercase;
      letter-spacing: 1px;
    }

    .phisguard-analysis-sections {
      margin-bottom: 24px;
    }

    .phisguard-analysis-section {
      margin-bottom: 16px;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      overflow: hidden;
    }

    .phisguard-analysis-header {
      background: #f8f9fa;
      padding: 12px 16px;
      font-weight: 600;
      color: #495057;
      border-bottom: 1px solid #dee2e6;
    }

    .phisguard-analysis-content {
      padding: 16px;
    }

    .phisguard-analysis-content ul {
      margin: 0;
      padding-left: 20px;
    }

    .phisguard-analysis-content li {
      margin-bottom: 4px;
      color: #495057;
    }

    .phisguard-recommendations {
      margin-bottom: 24px;
    }

    .phisguard-recommendations h3 {
      margin: 0 0 12px 0;
      color: #495057;
    }

    .recommendations-content {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      padding: 16px;
      line-height: 1.5;
    }

    .phisguard-modal-footer {
      padding: 20px 24px;
      border-top: 1px solid #dee2e6;
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }

    .phisguard-btn {
      padding: 10px 20px;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .phisguard-btn-secondary {
      background: #6c757d;
      color: white;
    }

    .phisguard-btn-secondary:hover {
      background: #5a6268;
    }

    .phisguard-btn-primary {
      background: #007bff;
      color: white;
      border-color: #007bff;
    }

    .phisguard-btn-primary:hover {
      background: #0056b3;
    }

    @media (max-width: 600px) {
      .phisguard-modal-content {
        margin: 10px;
        max-height: calc(100vh - 20px);
      }

      .phisguard-modal-header,
      .phisguard-modal-body,
      .phisguard-modal-footer {
        padding: 16px;
      }

      .phisguard-modal-footer {
        flex-direction: column;
      }

      .phisguard-btn {
        width: 100%;
      }
    }
  `;

  // Add event listeners to buttons
  const closeButtons = modal.querySelectorAll('.phisguard-modal-close, .phisguard-btn-secondary');
  const openPhisGuardButton = modal.querySelector('.phisguard-btn-primary');

  const closeSecurityModal = function() {
    modal.remove();
    style.remove();
  };

  const openPhisGuardPopup = function(url) {
    chrome.runtime.sendMessage({
      action: 'openPopup',
      data: { url: url }
    });
    closeSecurityModal();
  };

  // Add close functionality to all close buttons
  closeButtons.forEach(button => {
    button.addEventListener('click', closeSecurityModal);
  });

  // Add open popup functionality
  if (openPhisGuardButton) {
    openPhisGuardButton.addEventListener('click', () => openPhisGuardPopup(url));
  }

  // Add functions to window as backup
  window.closeSecurityModal = closeSecurityModal;
  window.openPhisGuardPopup = openPhisGuardPopup;

  document.head.appendChild(style);
  document.body.appendChild(modal);
}

// Function to render analysis section
function renderAnalysisSection(title, data) {
  if (!data) return '';

  let content = '';
  if (data.details && Array.isArray(data.details)) {
    content = `<ul>${data.details.map(detail => `<li>${detail}</li>`).join('')}</ul>`;
  } else if (data.risk_flags && Array.isArray(data.risk_flags)) {
    content = `<ul>${data.risk_flags.map(flag => `<li>${flag}</li>`).join('')}</ul>`;
  } else if (data.error) {
    content = `<div style="color: #dc3545; padding: 12px; background: #f8d7da; border-radius: 4px; border: 1px solid #f5c6cb;">
      <strong>Analysis Unavailable</strong><br>
      ${data.error}
    </div>`;
  } else {
    content = '<div style="color: #6c757d; padding: 12px; background: #f8f9fa; border-radius: 4px; border: 1px solid #dee2e6;">' +
      '<strong>Analysis Pending</strong><br>' +
      'Security analysis temporarily unavailable. Please try again later.' +
      '</div>';
  }

  return `
    <div class="phisguard-analysis-section">
      <div class="phisguard-analysis-header">${title}</div>
      <div class="phisguard-analysis-content">${content}</div>
    </div>
  `;
}

// Function to get security recommendations
function getSecurityRecommendations(recommendation) {
  switch (recommendation) {
    case 'danger':
      return `
        <strong>🚨 HIGH RISK - Take immediate action:</strong><br>
        • Do not enter any personal information or passwords<br>
        • Do not click on any links or download files<br>
        • Leave this website immediately<br>
        • Report this URL to your security team<br>
        • Consider running a security scan on your device
      `;
    case 'caution':
      return `
        <strong>⚠️ MEDIUM RISK - Proceed with caution:</strong><br>
        • Verify the website URL carefully<br>
        • Be cautious with any forms or downloads<br>
        • Check for HTTPS security indicators<br>
        • Consider using alternative trusted sources<br>
        • Monitor your device for unusual activity
      `;
    default:
      return `
        <strong>✅ LOW RISK - Generally safe:</strong><br>
        • Continue with normal browsing caution<br>
        • Verify information from multiple sources if needed<br>
        • Keep your security software updated<br>
        • Report any suspicious behavior you notice
      `;
  }
}

// Function to show error modal
function showErrorModal(message) {
  const modal = document.createElement('div');
  modal.id = 'phisguard-error-modal';
  modal.innerHTML = `
    <div class="phisguard-modal-overlay">
      <div class="phisguard-modal-content" style="max-width: 400px;">
        <div class="phisguard-modal-header danger-header">
          <div class="phisguard-modal-title">
            <span class="phisguard-modal-icon">⚠️</span>
            <h2>Error</h2>
          </div>
          <button class="phisguard-modal-close" onclick="this.closest('#phisguard-error-modal').remove()">×</button>
        </div>
        <div class="phisguard-modal-body">
          <p style="margin: 0; color: #495057; line-height: 1.5;">${message}</p>
        </div>
        <div class="phisguard-modal-footer">
          <button class="phisguard-btn phisguard-btn-secondary" onclick="this.closest('#phisguard-error-modal').remove()">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
}

// Listen for messages from background script (if needed for updates)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'refreshIndicators') {
    // Re-scan all links
    const links = document.querySelectorAll('a');
    processLinks(links);
  }
});