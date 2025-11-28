#!/usr/bin/env python3
"""
Script to fetch phishing data from PhishTank API and prepare it for model training.
"""

import requests
import json
import pandas as pd
import time
import os
import sys
from datetime import datetime, timedelta
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.feature_extractor import extract_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PhishTankFetcher:
    """Fetch phishing data from PhishTank API."""

    def __init__(self, api_url="https://data.phishtank.com/data/online-valid.json"):
        self.api_url = api_url
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)

    def fetch_phishing_data(self, max_urls=1000) -> pd.DataFrame:
        """
        Fetch phishing URLs from PhishTank API.

        Args:
            max_urls: Maximum number of URLs to fetch

        Returns:
            DataFrame with phishing URLs and metadata
        """
        logger.info("Fetching phishing data from PhishTank...")

        try:
            response = requests.get(self.api_url, timeout=30)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Retrieved {len(data)} phishing entries from PhishTank")

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Filter and clean data
            if len(df) > max_urls:
                df = df.head(max_urls)

            # Extract relevant columns
            phishing_data = []
            for _, row in df.iterrows():
                try:
                    url = row.get('url', '')
                    if url:
                        phishing_data.append({
                            'url': url,
                            'label': 1,  # 1 = phishing
                            'source': 'phishtank',
                            'submission_time': row.get('submission_time', ''),
                            'verified': row.get('verified', ''),
                            'verification_time': row.get('verification_time', ''),
                            'online': row.get('online', ''),
                            'target': row.get('target', ''),
                            'details': json.dumps({
                                'phish_id': row.get('phish_id', ''),
                                'phish_detail_url': row.get('phish_detail_url', ''),
                                'submission_time': row.get('submission_time', ''),
                                'verification_time': row.get('verification_time', ''),
                            })
                        })
                except Exception as e:
                    logger.warning(f"Error processing PhishTank entry: {e}")
                    continue

            phishing_df = pd.DataFrame(phishing_data)
            logger.info(f"Processed {len(phishing_df)} phishing URLs")
            return phishing_df

        except Exception as e:
            logger.error(f"Error fetching PhishTank data: {e}")
            return pd.DataFrame()

    def fetch_legitimate_urls(self, count=1000) -> pd.DataFrame:
        """
        Generate or fetch legitimate URLs for balanced training.
        For demo purposes, we'll use a predefined list of legitimate domains.
        """
        logger.info("Generating legitimate URL samples...")

        # Predefined list of legitimate domains (expand as needed)
        legitimate_domains = [
            'google.com', 'github.com', 'stackoverflow.com', 'wikipedia.org',
            'amazon.com', 'microsoft.com', 'apple.com', 'facebook.com',
            'twitter.com', 'linkedin.com', 'youtube.com', 'instagram.com',
            'reddit.com', 'netflix.com', 'paypal.com', 'ebay.com',
            'yahoo.com', 'bing.com', 'duckduckgo.com', 'mozilla.org',
            'python.org', 'npmjs.com', 'docker.com', 'kubernetes.io',
            'aws.amazon.com', 'azure.microsoft.com', 'cloud.google.com'
        ]

        legitimate_data = []
        for domain in legitimate_domains:
            # Generate various URL patterns
            urls = [
                f'https://{domain}',
                f'https://{domain}/login',
                f'https://{domain}/account',
                f'https://{domain}/profile',
                f'https://{domain}/settings',
                f'https://www.{domain}',
                f'https://www.{domain}/about',
                f'https://www.{domain}/contact'
            ]

            for url in urls:
                legitimate_data.append({
                    'url': url,
                    'label': 0,  # 0 = legitimate
                    'source': 'legitimate',
                    'submission_time': datetime.now().isoformat(),
                    'verified': 'yes',
                    'verification_time': datetime.now().isoformat(),
                    'online': 'yes',
                    'target': domain,
                    'details': json.dumps({'generated': True})
                })

                if len(legitimate_data) >= count:
                    break
            if len(legitimate_data) >= count:
                break

        legitimate_df = pd.DataFrame(legitimate_data[:count])
        logger.info(f"Generated {len(legitimate_df)} legitimate URLs")
        return legitimate_df

    def combine_datasets(self, phishing_df: pd.DataFrame, legitimate_df: pd.DataFrame) -> pd.DataFrame:
        """Combine phishing and legitimate datasets."""
        combined_df = pd.concat([phishing_df, legitimate_df], ignore_index=True)
        combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)  # Shuffle
        return combined_df

    def extract_features_for_training(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract features from URLs for ML training.

        Args:
            df: DataFrame with 'url' and 'label' columns

        Returns:
            DataFrame with features and labels
        """
        logger.info(f"Extracting features from {len(df)} URLs...")

        feature_data = []
        for idx, row in df.iterrows():
            try:
                url = str(row['url'])
                features = extract_features(url)
                features['label'] = int(row['label'])
                features['original_url'] = url
                features['source'] = row.get('source', 'unknown')
                feature_data.append(features)

                if (idx + 1) % 100 == 0:
                    logger.info(f"Processed {idx + 1}/{len(df)} URLs")

            except Exception as e:
                logger.warning(f"Failed to extract features for URL {idx}: {e}")
                continue

        feature_df = pd.DataFrame(feature_data)
        logger.info(f"Successfully extracted features for {len(feature_df)} URLs")
        return feature_df

    def save_dataset(self, df: pd.DataFrame, filename: str):
        """Save dataset to CSV file."""
        filepath = os.path.join(self.data_dir, filename)
        df.to_csv(filepath, index=False)
        logger.info(f"Saved dataset to {filepath}")

    def load_existing_dataset(self, filename: str) -> pd.DataFrame:
        """Load existing dataset if it exists."""
        filepath = os.path.join(self.data_dir, filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            logger.info(f"Loaded existing dataset from {filepath} ({len(df)} samples)")
            return df
        return pd.DataFrame()

def main():
    """Main function to fetch and prepare training data."""
    try:
        fetcher = PhishTankFetcher()

        # Check for existing dataset
        existing_file = "latest_training_data.csv"
        existing_df = fetcher.load_existing_dataset(existing_file)

        if not existing_df.empty:
            print(f"Found existing dataset with {len(existing_df)} samples")
            use_existing = input("Use existing dataset? (y/n): ").lower().strip()
            if use_existing == 'y':
                training_df = existing_df
            else:
                # Fetch new data
                print("Fetching new phishing data...")
                phishing_df = fetcher.fetch_phishing_data(max_urls=2000)
                legitimate_df = fetcher.fetch_legitimate_urls(count=2000)
                combined_df = fetcher.combine_datasets(phishing_df, legitimate_df)
                training_df = fetcher.extract_features_for_training(combined_df)
                fetcher.save_dataset(training_df, existing_file)
        else:
            # Fetch new data
            print("Fetching phishing data from PhishTank...")
            phishing_df = fetcher.fetch_phishing_data(max_urls=2000)

            print("Generating legitimate URLs...")
            legitimate_df = fetcher.fetch_legitimate_urls(count=2000)

            print("Combining datasets...")
            combined_df = fetcher.combine_datasets(phishing_df, legitimate_df)

            print("Extracting features for training...")
            training_df = fetcher.extract_features_for_training(combined_df)

            fetcher.save_dataset(training_df, existing_file)

        # Display statistics
        print("\n" + "="*60)
        print("DATASET STATISTICS")
        print("="*60)
        print(f"Total samples: {len(training_df)}")
        print(f"Phishing samples: {len(training_df[training_df['label'] == 1])}")
        print(f"Legitimate samples: {len(training_df[training_df['label'] == 0])}")
        print(".2%")

        # Save raw URLs for reference
        raw_urls_df = training_df[['original_url', 'label', 'source']].copy()
        fetcher.save_dataset(raw_urls_df, "latest_raw_urls.csv")

        print("\n✅ Dataset preparation completed!")
        print(f"Training data saved to: {os.path.join(fetcher.data_dir, existing_file)}")
        print(f"Raw URLs saved to: {os.path.join(fetcher.data_dir, 'latest_raw_urls.csv')}")

    except Exception as e:
        logger.error(f"Dataset preparation failed: {e}")
        print(f"\n❌ Dataset preparation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()