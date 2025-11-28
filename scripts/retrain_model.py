#!/usr/bin/env python3
"""
Automated retraining pipeline for ML phishing detection models.
Combines user feedback, fresh phishing data, and existing training data.
"""

import sys
import os
import pandas as pd
import json
from datetime import datetime, timedelta
import logging
import shutil
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ml_detector import detector
from services.email_text_detector import email_detector
from scripts.fetch_phishtank_data import PhishTankFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelRetrainer:
    """Handles automated model retraining with new data."""

    def __init__(self):
        self.data_dir = "data"
        self.models_dir = "models"
        self.backup_dir = os.path.join(self.models_dir, "backups")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

    def load_user_feedback(self) -> pd.DataFrame:
        """Load user feedback data for retraining."""
        feedback_file = os.path.join(self.data_dir, 'user_feedback.jsonl')
        feedback_data = []

        if os.path.exists(feedback_file):
            with open(feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        feedback_item = json.loads(line.strip())
                        # Convert user correction to numeric label
                        correction = feedback_item.get('user_correction', '').lower()
                        if correction in ['phishing', 'malicious']:
                            label = 1
                        elif correction in ['legitimate', 'safe']:
                            label = 0
                        else:
                            continue  # Skip unclear feedback

                        feedback_data.append({
                            'url': feedback_item['url'],
                            'label': label,
                            'source': 'user_feedback',
                            'original_risk_score': feedback_item.get('original_risk_score'),
                            'timestamp': feedback_item.get('timestamp')
                        })
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Error parsing feedback line: {e}")
                        continue

        df = pd.DataFrame(feedback_data)
        logger.info(f"Loaded {len(df)} user feedback items")
        return df

    def load_existing_training_data(self) -> pd.DataFrame:
        """Load existing training data."""
        training_files = [
            'balanced_training_data.csv',
            'balanced_training_data_processed.csv',
            os.path.join(self.data_dir, 'latest_training_data.csv')
        ]

        for file_path in training_files:
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                    logger.info(f"Loaded existing training data from {file_path} ({len(df)} samples)")
                    return df
                except Exception as e:
                    logger.warning(f"Error loading {file_path}: {e}")
                    continue

        logger.warning("No existing training data found")
        return pd.DataFrame()

    def fetch_fresh_data(self) -> pd.DataFrame:
        """Fetch fresh phishing data from external sources."""
        fetcher = PhishTankFetcher()

        # Fetch new phishing data
        phishing_df = fetcher.fetch_phishing_data(max_urls=500)

        # Generate legitimate URLs
        legitimate_df = fetcher.fetch_legitimate_urls(count=500)

        # Combine datasets
        combined_df = fetcher.combine_datasets(phishing_df, legitimate_df)

        # Extract features
        feature_df = fetcher.extract_features_for_training(combined_df)

        logger.info(f"Fetched {len(feature_df)} fresh training samples")
        return feature_df

    def combine_training_data(self, existing_df: pd.DataFrame, feedback_df: pd.DataFrame,
                            fresh_df: pd.DataFrame) -> pd.DataFrame:
        """Combine all training data sources."""
        dataframes = []

        # Add existing data (reduce weight to avoid overfitting)
        if not existing_df.empty:
            # Sample a subset of existing data to balance with new data
            sample_size = min(len(existing_df), 2000)
            existing_sample = existing_df.sample(n=sample_size, random_state=42)
            dataframes.append(existing_sample)

        # Add user feedback (highest priority)
        if not feedback_df.empty:
            # Convert feedback to feature vectors
            feedback_features = []
            for _, row in feedback_df.iterrows():
                try:
                    from services.feature_extractor import extract_features
                    features = extract_features(row['url'])
                    features['label'] = row['label']
                    features['source'] = 'user_feedback'
                    feedback_features.append(features)
                except Exception as e:
                    logger.warning(f"Error extracting features from feedback URL: {e}")
                    continue

            feedback_df_processed = pd.DataFrame(feedback_features)
            dataframes.append(feedback_df_processed)

        # Add fresh data
        if not fresh_df.empty:
            dataframes.append(fresh_df)

        if not dataframes:
            raise ValueError("No training data available")

        # Combine all data
        combined_df = pd.concat(dataframes, ignore_index=True)

        # Remove duplicates based on URL
        if 'original_url' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['original_url'])

        # Shuffle the data
        combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)

        logger.info(f"Combined training dataset: {len(combined_df)} samples")
        logger.info(f"Label distribution: {combined_df['label'].value_counts().to_dict()}")

        return combined_df

    def backup_current_model(self) -> str:
        """Backup current model files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"model_backup_{timestamp}")

        os.makedirs(backup_path, exist_ok=True)

        # Backup URL model
        url_model_files = ['phishing_model.pkl']
        for filename in url_model_files:
            src = os.path.join(self.models_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(backup_path, filename))

        # Backup email model
        email_model_files = ['email_text_model.pkl', 'email_text_vectorizer.pkl']
        for filename in email_model_files:
            src = os.path.join(self.models_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(backup_path, filename))

        logger.info(f"Model backup created at {backup_path}")
        return backup_path

    def retrain_url_model(self, training_data: pd.DataFrame) -> Dict:
        """Retrain the URL phishing detection model."""
        logger.info("Retraining URL phishing detection model...")

        try:
            # Train the model
            results = detector.train_model(training_data)

            logger.info("URL model retraining completed successfully")
            return results

        except Exception as e:
            logger.error(f"Error retraining URL model: {e}")
            raise

    def retrain_email_model(self, email_training_data: Optional[str] = None) -> Dict:
        """Retrain the email text detection model."""
        logger.info("Retraining email text detection model...")

        try:
            # Use existing email training data or default
            training_file = email_training_data or 'email_training_data.csv'
            results = email_detector.train_model(training_file)

            logger.info("Email model retraining completed successfully")
            return results

        except Exception as e:
            logger.error(f"Error retraining email model: {e}")
            raise

    def save_training_metadata(self, metadata: Dict):
        """Save training metadata for tracking."""
        metadata_file = os.path.join(self.data_dir, 'training_metadata.jsonl')

        metadata_entry = {
            'timestamp': datetime.now().isoformat(),
            'version': metadata.get('version', 'unknown'),
            **metadata
        }

        with open(metadata_file, 'a', encoding='utf-8') as f:
            json.dump(metadata_entry, f, ensure_ascii=False)
            f.write('\n')

        logger.info("Training metadata saved")

    def should_retrain(self, min_feedback_threshold: int = 10) -> bool:
        """Check if retraining should be performed."""
        feedback_df = self.load_user_feedback()

        # Check if we have enough new feedback
        if len(feedback_df) >= min_feedback_threshold:
            logger.info(f"Sufficient feedback collected ({len(feedback_df)} items), triggering retraining")
            return True

        # Check if it's been too long since last training (e.g., weekly)
        metadata_file = os.path.join(self.data_dir, 'training_metadata.jsonl')
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_training = json.loads(lines[-1])
                        last_training_date = datetime.fromisoformat(last_training['timestamp'])
                        days_since_training = (datetime.now() - last_training_date).days

                        if days_since_training >= 7:  # Weekly retraining
                            logger.info(f"{days_since_training} days since last training, triggering retraining")
                            return True
            except Exception as e:
                logger.warning(f"Error checking training history: {e}")

        return False

def main():
    """Main retraining pipeline."""
    try:
        logger.info("Starting automated model retraining pipeline...")

        retrainer = ModelRetrainer()

        # Check if retraining is needed
        if not retrainer.should_retrain():
            logger.info("Retraining not needed at this time")
            return

        # Load data sources
        logger.info("Loading training data sources...")
        existing_data = retrainer.load_existing_training_data()
        feedback_data = retrainer.load_user_feedback()
        fresh_data = retrainer.fetch_fresh_data()

        # Combine training data
        combined_data = retrainer.combine_training_data(existing_data, feedback_data, fresh_data)

        # Backup current models
        backup_path = retrainer.backup_current_model()

        # Retrain models
        url_results = retrainer.retrain_url_model(combined_data)
        email_results = retrainer.retrain_email_model()

        # Save training metadata
        metadata = {
            'version': datetime.now().strftime("%Y%m%d_%H%M%S"),
            'backup_path': backup_path,
            'total_samples': len(combined_data),
            'feedback_samples': len(feedback_data),
            'fresh_samples': len(fresh_data),
            'existing_samples': len(existing_data),
            'url_model_accuracy': url_results.get('accuracy'),
            'email_model_accuracy': email_results.get('accuracy')
        }

        retrainer.save_training_metadata(metadata)

        # Save updated training data
        output_file = os.path.join(retrainer.data_dir, f"training_data_{metadata['version']}.csv")
        combined_data.to_csv(output_file, index=False)

        logger.info("="*60)
        logger.info("MODEL RETRAINING COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        logger.info(f"Version: {metadata['version']}")
        logger.info(f"Total training samples: {metadata['total_samples']}")
        logger.info(f"URL Model Accuracy: {metadata['url_model_accuracy']:.4f}")
        logger.info(f"Email Model Accuracy: {metadata['email_model_accuracy']:.4f}")
        logger.info(f"Models backed up to: {backup_path}")
        logger.info(f"Updated training data saved to: {output_file}")

    except Exception as e:
        logger.error(f"Retraining pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()