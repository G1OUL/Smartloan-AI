import sys
import os
import sqlite3
# Import elements from app.py to verify
sys.path.append(os.path.dirname(__file__))
from app import calculate_emi, evaluate_loan_offers
def run_tests():
    print("==================================================")
    print("SmartLoan AI Rule Engine Verification Suite")
    print("==================================================")
    
    # 1. Test EMI Calculation
    print("\n[TEST 1] Verifying EMI Calculations...")
    test_p = 500000
    test_r = 9.5
    test_t = 5
    calculated = calculate_emi(test_p, test_r, test_t)
    expected = 10500.95  # Standard PMT math for 5 Lakhs @ 9.5% for 5 Years
    
    print(f"Loan Amount: ₹{test_p:,}")
    print(f"Interest Rate: {test_r}% p.a.")
    print(f"Tenure: {test_t} Years (60 Months)")
    print(f"Calculated EMI: ₹{calculated}")
    print(f"Expected EMI:   ₹{expected}")
    
    assert abs(calculated - expected) < 1.0, f"EMI Calculation Error: expected {expected}, got {calculated}"
    print("✔ EMI Calculation math validated.")
    # 2. Test Eligibility Rule Evaluation
    print("\n[TEST 2] Verifying Eligibility & AI Scoring for a Prime Borrower...")
    # Profile: Salaried, 750 CIBIL (Very Good), ₹60,000 monthly income, ₹5,000 current EMIs
    # Loan request: Personal Loan, ₹300,000, 3 Years
    offers = evaluate_loan_offers(
        income=60000.0,
        existing_emis=5000.0,
        credit_score=750,
        loan_amount=300000.0,
        tenure_years=3,
        loan_type='Personal',
        employment_type='Salaried'
    )
    
    print(f"Found {len(offers)} Personal Loan offers in system.")
    eligible_offers = [o for o in offers if o['is_eligible']]
    print(f"Eligible offers count: {len(eligible_offers)}")
    
    # Check that at least SBI Personal Loan is returned as eligible (CIBIL req is 720, income 25k, DTI max 0.50)
    sbi_offer = next((o for o in offers if 'SBI' in o['lender_name']), None)
    if sbi_offer:
        print(f"SBI Product Match: {sbi_offer['loan_name']}")
        print(f"  Eligibility: {sbi_offer['is_eligible']}")
        print(f"  Approval Prob: {sbi_offer['approval_probability']}%")
        print(f"  EMI: ₹{sbi_offer['monthly_emi']:,}")
        print(f"  Total Cost: ₹{sbi_offer['total_cost']:,}")
        assert sbi_offer['is_eligible'] == True, "SBI loan should be eligible for 750 CIBIL, 60k income."
        assert sbi_offer['approval_probability'] > 80, "Approval probability for excellent credit score should be high."
    else:
        print("❌ SBI Offer not found in seeded database.")
        sys.exit(1)
        
    print("✔ Prime borrower rules validated.")
    # 3. Test Rejection Checks (Low CIBIL)
    print("\n[TEST 3] Verifying Rejection Checks (Low Credit Score)...")
    # Profile: Salaried, 550 CIBIL (Low), ₹80,000 income, ₹0 EMIs
    offers_low_cibil = evaluate_loan_offers(
        income=80000.0,
        existing_emis=0.0,
        credit_score=550,
        loan_amount=200000.0,
        tenure_years=2,
        loan_type='Personal',
        employment_type='Salaried'
    )
    
    for offer in offers_low_cibil:
        # Check that high-cibil requirement products are rejected
        if 'HDFC' in offer['lender_name']:  # HDFC Personal needs 750
            print(f"HDFC Product Match (Low CIBIL): {offer['loan_name']}")
            print(f"  Eligibility: {offer['is_eligible']}")
            print(f"  Rejection reasons: {offer['rejection_reasons']}")
            assert offer['is_eligible'] == False, "HDFC Personal should be rejected for 550 CIBIL."
            
    print("✔ Low Credit Score checks validated.")
    # 4. Test Rejection Checks (High DTI)
    print("\n[TEST 4] Verifying Rejection Checks (High DTI)...")
    # Profile: Salaried, 800 CIBIL (Excellent), ₹30,000 income, ₹20,000 current EMIs
    # Loan: ₹5,000,000, 15 Years, Home Loan (monthly EMI will be around ₹45,000)
    # DTI will be (20000 + 45000) / 30000 = 2.16 (216% - far above any max_dti limit)
    offers_high_dti = evaluate_loan_offers(
        income=30000.0,
        existing_emis=20000.0,
        credit_score=800,
        loan_amount=5000000.0,
        tenure_years=15,
        loan_type='Home',
        employment_type='Salaried'
    )
    
    for offer in offers_high_dti:
        print(f"Home Loan Product Match (High DTI): {offer['loan_name']}")
        print(f"  Eligibility: {offer['is_eligible']}")
        print(f"  Rejection reasons: {offer['rejection_reasons']}")
        assert offer['is_eligible'] == False, "All products should be ineligible due to DTI exceeding limit."
        
    print("✔ High DTI checks validated.")
    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
if __name__ == '__main__':
    run_tests()
