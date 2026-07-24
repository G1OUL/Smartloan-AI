import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score
import joblib
def train_loan_model(clean_filepath, model_save_path):
    print("=== Starting Model Preprocessing and Training ===")
    
    if not os.path.exists(clean_filepath):
        print(f"Error: Clean dataset not found at {clean_filepath}. Run clean_dataset.py first.")
        return
    # 1. Load Clean Dataset
    df = pd.read_csv(clean_filepath)
    
    # Split into features (X) and label (y)
    X = df.drop(columns=['approved'])
    y = df['approved']
    
    # 2. Split dataset: 70% Train, 15% Validation, 15% Test
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.1765, random_state=42, stratify=y_train_val
    ) # 0.1765 of 85% is approx 15% of total
    
    print(f"Dataset split completed:")
    print(f"  - Training Set:   {len(X_train)} rows")
    print(f"  - Validation Set: {len(X_val)} rows")
    print(f"  - Testing Set:    {len(X_test)} rows")
    # 3. Define Preprocessing Pipeline
    categorical_features = ['loan_type', 'employment_type']
    
    # Use OneHotEncoder for categoricals, remainder 'passthrough' leaves numerical columns unchanged
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features)
        ],
        remainder='passthrough'
    )
    # 4. Build Random Forest Pipeline
    model_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=150, max_depth=12, random_state=42))
    ])
    # 5. Train Model
    print("\nTraining Random Forest model...")
    model_pipeline.fit(X_train, y_train)
    print("Model training complete.")
    # 6. Evaluate Model on Validation Set
    y_val_pred = model_pipeline.predict(X_val)
    y_val_proba = model_pipeline.predict_proba(X_val)[:, 1]
    
    val_acc = accuracy_score(y_val, y_val_pred)
    val_auc = roc_auc_score(y_val, y_val_proba)
    print("\n" + "="*40)
    print("        VALIDATION PERFORMANCE REPORT")
    print("="*40)
    print(f"Validation Accuracy:  {val_acc*100:.2f}%")
    print(f"Validation ROC-AUC:   {val_auc:.4f}")
    print("\nClassification Report (Validation):")
    print(classification_report(y_val, y_val_pred))
    print("="*40)
    # 7. Evaluate on Test Set (Final Benchmark)
    y_test_pred = model_pipeline.predict(X_test)
    y_test_proba = model_pipeline.predict_proba(X_test)[:, 1]
    
    test_acc = accuracy_score(y_test, y_test_pred)
    test_auc = roc_auc_score(y_test, y_test_proba)
    print("\n" + "="*40)
    print("        TEST PERFORMANCE BENCHMARK")
    print("="*40)
    print(f"Test Set Accuracy:    {test_acc*100:.2f}%")
    print(f"Test Set ROC-AUC:     {test_auc:.4f}")
    print("="*40)
    # 8. Save Pipeline Model
    joblib.dump(model_pipeline, model_save_path)
    print(f"\nTrained ML model pipeline successfully saved to: {model_save_path}\n")
if __name__ == '__main__':
    clean_path = os.path.join(os.path.dirname(__file__), 'loan_data_clean.csv')
    model_path = os.path.join(os.path.dirname(__file__), 'loan_classifier.pkl')
    train_loan_model(clean_path, model_path)