import os
import pandas as pd
def clean_loan_dataset(raw_filepath, clean_filepath):
    print(f"=== Starting Data Cleaning on: {raw_filepath} ===")
    
    if not os.path.exists(raw_filepath):
        print(f"Error: Raw dataset not found at {raw_filepath}. Run generate_dataset.py first.")
        return
    # Load dataset using Pandas
    df = pd.read_csv(raw_filepath)
    total_scanned = len(df)
    
    # 1. Deduplication
    initial_count = len(df)
    df = df.drop_duplicates()
    duplicates_removed = initial_count - len(df)
    # 2. Handle missing entries (drop rows with any NaNs)
    pre_nan_count = len(df)
    df = df.dropna()
    nans_removed = pre_nan_count - len(df)
    # 3. Boundary / Outlier checks
    # Credit score must be in range [300, 900]
    cibil_outliers = df[(df['credit_score'] < 300) | (df['credit_score'] > 900)]
    
    # Income, loan amount, and tenure must be positive. EMIs must be non-negative.
    income_outliers = df[df['income'] <= 0]
    emi_outliers = df[df['existing_emis'] < 0]
    amount_outliers = df[df['loan_amount'] <= 0]
    tenure_outliers = df[df['tenure_years'] <= 0]
    
    # Filter valid rows
    df_clean = df[
        (df['credit_score'] >= 300) & (df['credit_score'] <= 900) &
        (df['income'] > 0) &
        (df['existing_emis'] >= 0) &
        (df['loan_amount'] > 0) &
        (df['tenure_years'] > 0)
    ]
    
    outliers_removed = len(df) - len(df_clean)
    # Save cleaned data
    df_clean.to_csv(clean_filepath, index=False)
    # Summary stats
    print("\n" + "="*40)
    print("      LOAN DATA CLEANING SUMMARY REPORT")
    print("="*40)
    print(f"Total Rows Scanned:         {total_scanned}")
    print(f"Duplicate Rows Removed:     {duplicates_removed}")
    print(f"NaN Rows Dropped:           {nans_removed}")
    print(f"Outlier Rows Dropped:       {outliers_removed}")
    print(f"  - Credit Score failures:  {len(cibil_outliers)}")
    print(f"  - Negative Income:        {len(income_outliers)}")
    print(f"  - Negative EMIs:          {len(emi_outliers)}")
    print(f"  - Negative Loan Amount:   {len(amount_outliers)}")
    print(f"  - Negative Tenure:        {len(tenure_outliers)}")
    print(f"Remaining Clean Records:    {len(df_clean)}")
    print("="*40)
    print(f"Cleaned dataset saved at: {clean_filepath}\n")
if __name__ == '__main__':
    raw_path = os.path.join(os.path.dirname(__file__), 'loan_data_raw.csv')
    clean_path = os.path.join(os.path.dirname(__file__), 'loan_data_clean.csv')
    clean_loan_dataset(raw_path, clean_path)
