#!/usr/bin/env python3
"""
Debug script for ML detector functionality
"""
import sys
import os
import traceback

# Add current directory to Python path
sys.path.append('.')

def test_model_loading():
    """Test if the model can be loaded"""
    print("=" * 50)
    print("TESTING MODEL LOADING")
    print("=" * 50)
    
    try:
        from services.ml_detector import detector
        print(f"✓ ML detector imported successfully")
        print(f"  Model loaded: {detector.model is not None}")
        print(f"  Current version: {detector.current_version}")
        print(f"  Model path: {detector.base_model_path}")
        print(f"  Model exists: {os.path.exists(detector.base_model_path)}")
        
        if detector.model is not None:
            print(f"  Model type: {type(detector.model)}")
            print(f"  Feature names count: {len(detector.feature_names)}")
            print(f"  Feature names: {detector.feature_names}")
        else:
            print("  ❌ No model loaded - this is the problem!")
            
        return detector.model is not None
        
    except Exception as e:
        print(f"❌ Error loading ML detector: {e}")
        print("Traceback:")
        traceback.print_exc()
        return False

def test_feature_extraction():
    """Test if features can be extracted"""
    print("\n" + "=" * 50)
    print("TESTING FEATURE EXTRACTION")
    print("=" * 50)
    
    try:
        from services.feature_extractor import extract_features
        
        test_url = "http://httpforever.com/"
        print(f"Testing URL: {test_url}")
        
        features = extract_features(test_url)
        print(f"✓ Features extracted successfully")
        print(f"  Features count: {len(features)}")
        print(f"  Sample features: {list(features.items())[:5]}")
        
        # Check if features match expected format
        expected_features = 21  # Should match ML detector feature_names
        if len(features) == expected_features:
            print(f"✓ Feature count matches expected ({expected_features})")
        else:
            print(f"❌ Feature count mismatch: {len(features)} vs {expected_features}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error extracting features: {e}")
        print("Traceback:")
        traceback.print_exc()
        return False

def test_prediction():
    """Test if prediction works"""
    print("\n" + "=" * 50)
    print("TESTING PREDICTION")
    print("=" * 50)
    
    try:
        from services.ml_detector import detector
        from services.feature_extractor import extract_features
        
        test_url = "http://httpforever.com/"
        print(f"Testing URL: {test_url}")
        
        # Extract features
        features = extract_features(test_url)
        print(f"✓ Features extracted")
        
        # Test prediction
        if detector.model is None:
            print("❌ No model loaded, skipping prediction test")
            return False
            
        print("Testing prediction...")
        probability = detector.predict(features)
        print(f"✓ Prediction successful!")
        print(f"  Phishing probability: {probability:.4f}")
        print(f"  Risk contribution: {int(probability * 100)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in prediction: {e}")
        print("Traceback:")
        traceback.print_exc()
        return False

def test_url_checker():
    """Test the full URL checker integration"""
    print("\n" + "=" * 50)
    print("TESTING URL CHECKER INTEGRATION")
    print("=" * 50)
    
    try:
        from services.url_checker import check_url
        
        test_url = "http://httpforever.com/"
        print(f"Testing URL: {test_url}")
        
        risk_score, details = check_url(test_url)
        print(f"✓ URL checker completed")
        print(f"  Risk score: {risk_score}")
        print(f"  Details count: {len(details)}")
        
        # Check if ML is mentioned in details
        ml_mentions = [d for d in details if 'ML' in d or 'Model' in d]
        if ml_mentions:
            print(f"  ML mentions in details: {ml_mentions}")
        else:
            print("  ❌ No ML mentions in details - ML may not be working")
            
        return True
        
    except Exception as e:
        print(f"❌ Error in URL checker: {e}")
        print("Traceback:")
        traceback.print_exc()
        return False

def main():
    """Run all debug tests"""
    print("PhisGuard ML Detector Debug Tests")
    print("=" * 50)
    
    results = []
    
    # Test model loading
    results.append(("Model Loading", test_model_loading()))
    
    # Test feature extraction
    results.append(("Feature Extraction", test_feature_extraction()))
    
    # Test prediction (only if model loads)
    if results[0][1]:  # If model loading succeeded
        results.append(("Prediction", test_prediction()))
    
    # Test URL checker integration
    results.append(("URL Checker Integration", test_url_checker()))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed < len(results):
        print("\nIssues found! Check the failing tests above.")
    else:
        print("\nAll tests passed! ML detector should be working.")

if __name__ == "__main__":
    main()