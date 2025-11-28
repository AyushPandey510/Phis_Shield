#!/usr/bin/env python3
"""
Script to train the ML email text phishing detection model.
"""

import sys
import os
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.email_text_detector import email_detector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_data(csv_path: str):
    """
    Create sample training data for demonstration.
    In production, use real phishing email datasets.
    """
    logger.info(f"Creating sample training data at {csv_path}")

    # Sample phishing emails
    phishing_emails = [
        {
            "text": "Urgent: Your account has been suspended. Click here to verify: http://fakebank.com/login",
            "label": 1
        },
        {
            "text": "Congratulations! You've won $1,000,000. Claim your prize now: http://lottery-scam.com/claim",
            "label": 1
        },
        {
            "text": "Your package is delayed. Update shipping info: http://amazon-fake.com/track",
            "label": 1
        },
        {
            "text": "Security Alert: Unusual login detected. Confirm identity: http://paypal-security.com/verify",
            "label": 1
        },
        {
            "text": "OTP Required: Your one-time password is 123456. Do not share.",
            "label": 1
        },
        {
            "text": "Important: Update your payment information immediately to avoid service interruption.",
            "label": 1
        }
    ]

    # Sample legitimate emails
    legitimate_emails = [
        {
            "text": "Meeting reminder: Team standup at 10 AM tomorrow in conference room A.",
            "label": 0
        },
        {
            "text": "Your order #12345 has been shipped. Track it here: https://amazon.com/track",
            "label": 0
        },
        {
            "text": "Weekly newsletter: Check out our latest blog posts and updates.",
            "label": 0
        },
        {
            "text": "Invoice for services rendered in October 2023.",
            "label": 0
        },
        {
            "text": "Thank you for your recent purchase. Here's your receipt.",
            "label": 0
        },
        {
            "text": "Project update: The new feature deployment is scheduled for next week.",
            "label": 0
        }
    ]

    # Combine and create DataFrame
    all_emails = phishing_emails + legitimate_emails
    df = pd.DataFrame(all_emails)

    # Save to CSV
    df.to_csv(csv_path, index=False)
    logger.info(f"Created sample dataset with {len(df)} emails ({len(phishing_emails)} phishing, {len(legitimate_emails)} legitimate)")

    return csv_path

def main():
    """Train the email text ML model using sample data."""
    try:
        logger.info("Starting email text ML model training...")

        # Create sample training data (in production, use real datasets)
        data_path = 'email_training_data.csv'
        if not os.path.exists(data_path):
            create_sample_data(data_path)
        else:
            logger.info(f"Using existing training data from {data_path}")

        # Train the model
        results = email_detector.train_model(data_path)

        # Print results
        print("\n" + "="*50)
        print("EMAIL TEXT ML MODEL TRAINING RESULTS")
        print("="*50)
        print(".4f")
        print(f"Training samples: {results['training_samples']}")
        print(f"Test samples: {results['test_samples']}")

        print("\nClassification Report:")
        report = results['classification_report']
        print(".4f")
        print(".4f")
        print(".4f")
        print(".4f")

        print("\n✅ Email text model trained and saved successfully!")
        print("The model will be automatically loaded by the backend.")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        print(f"\n❌ Training failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()