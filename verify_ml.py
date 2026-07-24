import os
import sys
import joblib
import pandas as pd
def run_ml_verification():
    print("==================================================")
    print("SmartLoan AI Machine Learning Verification Suite")
    print("==================================================")
    # Imports from project
    from generate_dataset import generate_loan_dataset
    from clean_dataset import clean_loan_dataset
    from train_model import train_loan_model
    # Paths
    raw_csv = 'loan_data_raw_test.csv'
    clean_csv = 'loan_data_clean_test.csv'
    model_pkl = 'loan_classifier_test.pkl'
    # 1. Test Dataset Generation
    print("\n[STEP 1] Generating raw test dataset...")
    generate_loan_dataset(raw_csv, num_records=1000)
    assert os.path.exists(raw_csv), "Raw dataset file was not created!"
    print("✔ Raw dataset generation verified.")
    # 2. Test Dataset Cleaning
    print("\n[STEP 2] Cleaning raw test dataset...")
    clean_loan_dataset(raw_csv, clean_csv)
    assert os.path.exists(clean_csv), "Cleaned dataset file was not created!"
    print("✔ Dataset cleaning verified.")
    # 3. Test Model Training
    print("\n[STEP 3] Training model classifier...")
    train_loan_model(clean_csv, model_pkl)
    assert os.path.exists(model_pkl), "Trained model pickle file was not created!"
    print("✔ Model training and saving verified.")
    # 4. Test Model Loading & Predict
    print("\n[STEP 4] Loading model and running mock predictions...")
    model = joblib.load(model_pkl)
    
    # Create a test borrower profile
    test_borrower = pd.DataFrame([{
        'income': 50000.0,
        'existing_emis': 0.0,
        'credit_score': 780,
        'loan_amount': 200000.0,
        'tenure_years': 3,
        'loan_type': 'Personal',
        'employment_type': 'Salaried'
    }])
    probabilities = model.predict_proba(test_borrower)
    print("Test Borrower features:")
    print(test_borrower.to_dict('records')[0])
    print(f"Classifier prediction output (proba): {probabilities}")
    
    # probabilities[0][1] represents approval chance
    approval_chance = probabilities[0][1]
    print(f"Approval Probability: {approval_chance * 100:.1f}%")
    
    assert len(probabilities[0]) == 2, "Proba output should contain 2 classes (rejected, approved)."
    assert approval_chance > 0.70, "Excellent profile should have high approval chance!"
    print("✔ Model prediction logic verified.")
    # Clean up test files
    for file in [raw_csv, clean_csv, model_pkl]:
        if os.path.exists(file):
            os.remove(file)
            
    print("\n==================================================")
    print("ALL MACHINE LEARNING PIPELINE TESTS PASSED!")
    print("==================================================")
if __name__ == '__main__':
    # Ensure current directory is in search path
    sys.path.append(os.path.dirname(__file__))
    run_ml_verification()