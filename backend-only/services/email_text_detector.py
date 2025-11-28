import os
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
from typing import Dict, Any, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

class EmailTextDetector:
    """
    Machine Learning-based phishing email text detector using Naïve Bayes with TF-IDF.
    Supports model versioning for zero-downtime updates.
    """

    def __init__(self, model_path: str = 'models/email_text_model.pkl',
                 vectorizer_path: str = 'models/email_text_vectorizer.pkl',
                 version: str = 'latest'):
        self.base_model_path = model_path
        self.base_vectorizer_path = vectorizer_path
        self.current_version = version
        self.model: Optional[MultinomialNB] = None
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.versions_dir = 'models/versions'
        os.makedirs(self.versions_dir, exist_ok=True)
        self.load_model()

    def load_model(self) -> bool:
        """Load trained model and vectorizer if they exist, with version support."""
        try:
            model_path, vectorizer_path = self._get_model_paths()
            if os.path.exists(model_path) and os.path.exists(vectorizer_path):
                self.model = joblib.load(model_path)
                self.vectorizer = joblib.load(vectorizer_path)
                logger.info(f"Loaded email text model version '{self.current_version}' from {model_path}")
                return True
            else:
                logger.warning(f"Email text model version '{self.current_version}' not found")
                return False
        except Exception as e:
            logger.error(f"Error loading email text model: {e}")
            return False

    def _get_model_paths(self) -> tuple:
        """Get the model and vectorizer paths based on version."""
        if self.current_version == 'latest':
            return self.base_model_path, self.base_vectorizer_path
        else:
            base_dir = os.path.join(self.versions_dir, self.current_version)
            return (os.path.join(base_dir, 'email_text_model.pkl'),
                   os.path.join(base_dir, 'email_text_vectorizer.pkl'))

    def switch_version(self, version: str) -> bool:
        """Switch to a different model version."""
        old_version = self.current_version
        self.current_version = version

        if self.load_model():
            logger.info(f"Successfully switched email model from version '{old_version}' to '{version}'")
            return True
        else:
            # Revert on failure
            self.current_version = old_version
            self.load_model()
            logger.error(f"Failed to switch email model to version '{version}', reverted to '{old_version}'")
            return False

    def list_versions(self) -> List[str]:
        """List all available model versions."""
        versions = ['latest']

        if os.path.exists(self.versions_dir):
            for dirname in os.listdir(self.versions_dir):
                version_dir = os.path.join(self.versions_dir, dirname)
                if os.path.isdir(version_dir):
                    model_file = os.path.join(version_dir, 'email_text_model.pkl')
                    vectorizer_file = os.path.join(version_dir, 'email_text_vectorizer.pkl')
                    if os.path.exists(model_file) and os.path.exists(vectorizer_file):
                        versions.append(dirname)

        return sorted(versions, reverse=True)

    def save_version(self, version: str) -> bool:
        """Save current model as a specific version."""
        try:
            if self.model is None or self.vectorizer is None:
                logger.error("No model loaded to save")
                return False

            version_dir = os.path.join(self.versions_dir, version)
            os.makedirs(version_dir, exist_ok=True)

            model_path = os.path.join(version_dir, 'email_text_model.pkl')
            vectorizer_path = os.path.join(version_dir, 'email_text_vectorizer.pkl')

            joblib.dump(self.model, model_path)
            joblib.dump(self.vectorizer, vectorizer_path)
            logger.info(f"Saved email model as version '{version}' to {version_dir}")
            return True
        except Exception as e:
            logger.error(f"Error saving email model version '{version}': {e}")
            return False

    def preprocess_text(self, text: str) -> str:
        """Basic text preprocessing for email content."""
        if not isinstance(text, str):
            return ""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    def train_model(self, data_path: str = 'email_training_data.csv') -> Dict[str, Any]:
        """
        Train the ML model using the provided dataset.

        Args:
            data_path: Path to CSV file with columns: text, label (0=legitimate, 1=phishing)

        Returns:
            Dictionary with training results
        """
        try:
            logger.info(f"Loading training data from {data_path}")

            # Load data
            df = pd.read_csv(data_path)

            # Check if data has the expected structure
            if 'text' not in df.columns or 'label' not in df.columns:
                raise ValueError("Training data must have 'text' and 'label' columns")

            # Preprocess texts
            df['processed_text'] = df['text'].apply(self.preprocess_text)

            # Prepare features and labels
            X = df['processed_text']
            y = df['label']

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples")

            # Create and fit vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words='english'
            )

            X_train_tfidf = self.vectorizer.fit_transform(X_train)
            X_test_tfidf = self.vectorizer.transform(X_test)

            # Train model
            self.model = MultinomialNB()
            self.model.fit(X_train_tfidf, y_train)

            # Evaluate
            y_pred = self.model.predict(X_test_tfidf)
            accuracy = accuracy_score(y_test, y_pred)
            report = classification_report(y_test, y_pred, output_dict=True)

            logger.info(f"Model accuracy: {accuracy:.4f}")

            # Save model and vectorizer
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.vectorizer, self.vectorizer_path)
            logger.info(f"Saved model to {self.model_path} and vectorizer to {self.vectorizer_path}")

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
            logger.error(f"Error training email text model: {e}")
            raise

    def predict(self, subject: str, body: str) -> Tuple[float, Dict[str, Any]]:
        """
        Predict phishing probability for email content.

        Args:
            subject: Email subject line
            body: Email body text

        Returns:
            Tuple of (phishing_probability, analysis_dict)
        """
        if self.model is None or self.vectorizer is None:
            logger.warning("No email text model loaded, returning neutral score")
            return 0.5, {"error": "Model not loaded"}

        try:
            # Combine subject and body
            full_text = f"{subject} {body}"
            processed_text = self.preprocess_text(full_text)

            # Vectorize
            text_tfidf = self.vectorizer.transform([processed_text])

            # Get prediction probabilities
            probabilities = self.model.predict_proba(text_tfidf)[0]

            # Return probability of phishing (assuming 1 = phishing)
            phishing_prob = float(probabilities[1])

            # Get top features for analysis
            feature_names = self.vectorizer.get_feature_names_out()
            feature_importance = self.model.feature_log_prob_[1] - self.model.feature_log_prob_[0]

            # Get top phishing indicators
            top_indices = np.argsort(feature_importance)[-10:][::-1]  # Top 10
            top_features = [feature_names[i] for i in top_indices if i < len(feature_names)]

            analysis = {
                "phishing_probability": phishing_prob,
                "confidence": float(max(probabilities)),
                "top_phishing_indicators": top_features[:5],  # Top 5 for brevity
                "processed_text_length": len(processed_text),
                "risk_level": "low" if phishing_prob < 0.3 else "medium" if phishing_prob < 0.7 else "high"
            }

            return phishing_prob, analysis

        except Exception as e:
            logger.error(f"Error making email text prediction: {e}")
            return 0.5, {"error": str(e)}

# Global instance
email_detector = EmailTextDetector()