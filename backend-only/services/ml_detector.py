import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class PhishingDetector:
    """
    Machine Learning-based phishing URL detector using Random Forest.
    Supports model versioning for zero-downtime updates.
    """

    def __init__(self, model_path: str = 'models/phishing_model.pkl', version: str = 'latest'):
        self.base_model_path = model_path
        self.current_version = version
        self.model: Optional[RandomForestClassifier] = None
        self.feature_names = [
            'url_length', 'domain_length', 'subdomain_length', 'tld_length',
            'path_length', 'query_length', 'num_dots', 'num_hyphens',
            'num_slashes', 'num_question', 'num_equals', 'num_at',
            'num_percent', 'num_digits', 'has_https', 'kw_login',
            'kw_secure', 'kw_update', 'kw_verify', 'kw_payment', 'kw_account'
        ]
        self.versions_dir = 'models/versions'
        os.makedirs(self.versions_dir, exist_ok=True)
        self.load_model()

    def load_model(self) -> bool:
        """Load trained model if it exists, with version support."""
        try:
            model_path = self._get_model_path()
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                logger.info(f"Loaded ML model version '{self.current_version}' from {model_path}")
                return True
            else:
                logger.warning(f"ML model version '{self.current_version}' not found at {model_path}")
                return False
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            return False

    def _get_model_path(self) -> str:
        """Get the model path based on version."""
        if self.current_version == 'latest':
            return self.base_model_path
        else:
            return os.path.join(self.versions_dir, f"phishing_model_{self.current_version}.pkl")

    def switch_version(self, version: str) -> bool:
        """Switch to a different model version."""
        old_version = self.current_version
        self.current_version = version

        if self.load_model():
            logger.info(f"Successfully switched from version '{old_version}' to '{version}'")
            return True
        else:
            # Revert on failure
            self.current_version = old_version
            self.load_model()
            logger.error(f"Failed to switch to version '{version}', reverted to '{old_version}'")
            return False

    def list_versions(self) -> List[str]:
        """List all available model versions."""
        versions = ['latest']

        if os.path.exists(self.versions_dir):
            for filename in os.listdir(self.versions_dir):
                if filename.startswith('phishing_model_') and filename.endswith('.pkl'):
                    version = filename.replace('phishing_model_', '').replace('.pkl', '')
                    versions.append(version)

        return sorted(versions, reverse=True)

    def save_version(self, version: str) -> bool:
        """Save current model as a specific version."""
        try:
            if self.model is None:
                logger.error("No model loaded to save")
                return False

            version_path = os.path.join(self.versions_dir, f"phishing_model_{version}.pkl")
            os.makedirs(os.path.dirname(version_path), exist_ok=True)
            joblib.dump(self.model, version_path)
            logger.info(f"Saved model as version '{version}' to {version_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving model version '{version}': {e}")
            return False

    def train_model(self, data_path: str = 'balanced_training_data.csv') -> Dict[str, Any]:
        """
        Train the ML model using the provided dataset.

        Args:
            data_path: Path to CSV file with features and labels

        Returns:
            Dictionary with training results
        """
        try:
            logger.info(f"Loading training data from {data_path}")

            # Load data
            df = pd.read_csv(data_path)

            # Check if data has the expected structure
            if 'label' not in df.columns:
                raise ValueError("Training data must have a 'label' column")

            # Prepare features and labels
            X = df.drop('label', axis=1)
            y = df['label']

            # Ensure we have the right features
            missing_features = set(self.feature_names) - set(X.columns)
            if missing_features:
                raise ValueError(f"Missing features in training data: {missing_features}")

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X[self.feature_names], y, test_size=0.2, random_state=42, stratify=y
            )

            logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples")

            # Train model with reduced complexity to prevent overfitting
            self.model = RandomForestClassifier(
                n_estimators=50,  # Reduced from 100
                max_depth=10,     # Reduced from 20
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1
            )

            self.model.fit(X_train, y_train)

            # Evaluate
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            report = classification_report(y_test, y_pred, output_dict=True)

            logger.info(f"Model accuracy: {accuracy:.4f}")

            # Save model
            model_path = self._get_model_path()
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            joblib.dump(self.model, model_path)
            logger.info(f"Saved model to {model_path}")

            # Create a versioned backup
            from datetime import datetime
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.save_version(version)

            return {
                'accuracy': accuracy,
                'classification_report': report,
                'training_samples': len(X_train),
                'test_samples': len(X_test),
                'version': version
            }

        except Exception as e:
            logger.error(f"Error training model: {e}")
            raise

    def predict(self, features: Dict[str, float]) -> float:
        """
        Predict phishing probability for a URL based on its features.

        Args:
            features: Dictionary of feature values

        Returns:
            Probability of being phishing (0.0 to 1.0)
        """
        if self.model is None:
            logger.warning("No ML model loaded, returning neutral score")
            return 0.5

        try:
            # Convert features dict to DataFrame with proper column names to avoid sklearn warnings
            import pandas as pd
            feature_df = pd.DataFrame([features], columns=self.feature_names)

            # Get prediction probabilities
            probabilities = self.model.predict_proba(feature_df)[0]

            # Return probability of phishing (assuming 1 = phishing)
            phishing_prob = probabilities[1]

            return float(phishing_prob)

        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return 0.5

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance from the trained model."""
        if self.model is None:
            return None

        try:
            importance = self.model.feature_importances_
            return dict(zip(self.feature_names, importance))
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return None

# Global instance
detector = PhishingDetector()