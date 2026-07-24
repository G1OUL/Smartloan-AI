import os
import random
import csv
# Set random seed for reproducibility
random.seed(42)
def generate_loan_dataset(filepath, num_records=5000):
    print(f"=== Starting Synthetic Data Generation: {filepath} ===")
    
    # Header fields
    headers = [
        'income',
        'existing_emis',
        'credit_score',
        'loan_amount',
        'tenure_years',
        'loan_type',
        'employment_type',
        'approved'
    ]
    loan_types = ['Personal', 'Home', 'Education', 'Business']
    employment_types = ['Salaried', 'Self-Employed', 'Unemployed']
    records = []
    approved_count = 0
    rejected_count = 0
    for _ in range(num_records):
        # Generate random inputs mimicking a representative Indian applicant pool
        loan_type = random.choice(loan_types)
        employment_type = random.choices(employment_types, weights=[0.6, 0.3, 0.1])[0]
        # Monthly Net income in INR (typically between 12k and 200k)
        income = round(random.uniform(12000, 200000), -2)
        # Existing EMIs (some portion of income, usually 0 to 60%)
        emi_ratio = random.uniform(0, 0.6) if random.random() < 0.7 else 0.0
        existing_emis = round(income * emi_ratio, -2)
        # CIBIL Credit Score (300 to 900, higher density around 650-800)
        if random.random() < 0.8:
            credit_score = int(random.triangular(550, 900, 720))
        else:
            credit_score = int(random.uniform(300, 550))
        # Loan Amount requested
        if loan_type == 'Home':
            loan_amount = round(random.uniform(500000, 8000000), -4)
            tenure_years = random.randint(5, 30)
        elif loan_type == 'Business':
            loan_amount = round(random.uniform(100000, 3000000), -4)
            tenure_years = random.randint(1, 10)
        elif loan_type == 'Education':
            loan_amount = round(random.uniform(50000, 1500000), -4)
            tenure_years = random.randint(3, 15)
        else: # Personal
            loan_amount = round(random.uniform(30000, 1500000), -4)
            tenure_years = random.randint(1, 7)
        # Underwriting Rules to set ground truth label
        # Simple EMI proxy (approx 1% of loan amount monthly)
        new_emi_proxy = (loan_amount * 0.12 / 12)  # assuming ~12% interest p.a.
        total_obligations = existing_emis + new_emi_proxy
        dti = total_obligations / income
        # Base Approval Status
        is_approved = 1
        
        # Rule 1: Minimum CIBIL Score threshold
        if credit_score < 600:
            is_approved = 0
            
        # Rule 2: High Debt-to-Income (DTI) ratio
        elif dti > 0.55:
            is_approved = 0
        # Rule 3: Minimum Income requirements
        elif income < 15000:
            is_approved = 0
        # Rule 4: Employment restrictions
        elif employment_type == 'Unemployed' and loan_type != 'Education':
            # Unemployed only allowed for Education loans (student borrower + co-borrower income)
            is_approved = 0
        # Add 5% noise (random flips to simulate complex edge cases or manual overrides in banking)
        if random.random() < 0.05:
            is_approved = 1 - is_approved
        if is_approved == 1:
            approved_count += 1
        else:
            rejected_count += 1
        records.append([
            income,
            existing_emis,
            credit_score,
            loan_amount,
            tenure_years,
            loan_type,
            employment_type,
            is_approved
        ])
    # Write dataset to CSV
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(records)
    print(f"Generated {num_records} rows of raw borrower data.")
    print(f"  Approved: {approved_count} ({approved_count/num_records*100:.1f}%)")
    print(f"  Rejected: {rejected_count} ({rejected_count/num_records*100:.1f}%)")
    print(f"Dataset saved at: {filepath}\n")
if __name__ == '__main__':
    dataset_raw_path = os.path.join(os.path.dirname(__file__), 'loan_data_raw.csv')
    generate_loan_dataset(dataset_raw_path, 5000)