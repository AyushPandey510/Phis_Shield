#!/usr/bin/env python3
"""
Script to train the ML phishing detection model.
"""

import sys
import os
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ml_detector import detector
from services.feature_extractor import extract_features
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preprocess_data(csv_path: str) -> str:
    """
    Preprocess raw URL data into feature vectors for training.

    Args:
        csv_path: Path to CSV with columns: source, url, domain, tld, label

    Returns:
        Path to processed CSV with features
    """
    logger.info(f"Loading raw data from {csv_path}")

    # Load raw data
    df = pd.read_csv(csv_path)

    # Check required columns
    required_cols = ['url', 'label']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    logger.info(f"Processing {len(df)} URLs...")

    # Extract features for each URL
    feature_data = []
    for idx, row in df.iterrows():
        try:
            url = str(row['url'])
            features = extract_features(url)
            features['label'] = int(row['label'])
            feature_data.append(features)
        except Exception as e:
            logger.warning(f"Failed to process URL {idx}: {e}")
            continue

    # Create feature dataframe
    feature_df = pd.DataFrame(feature_data)

    # Save processed data
    processed_path = csv_path.replace('.csv', '_processed.csv')
    feature_df.to_csv(processed_path, index=False)

    logger.info(f"Saved processed data to {processed_path}")
    return processed_path

def main():
    """Train the ML model using the balanced training data."""
    try:
        logger.info("Starting ML model training...")

        # Preprocess raw data
        processed_data_path = preprocess_data('balanced_training_data.csv')

        # Train the model
        results = detector.train_model(processed_data_path)

        # Print results
        print("\n" + "="*50)
        print("ML MODEL TRAINING RESULTS")
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

        print("\n✅ Model trained and saved successfully!")
        print("The model will be automatically loaded by the backend.")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        print(f"\n❌ Training failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()