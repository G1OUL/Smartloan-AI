import os
import sys
import json
import sqlite3

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from init_db import init_db
from app import (
    app,
    calculate_emi,
    evaluate_loan_offers,
    get_or_train_ml_model
)

def run_suite():
    print("=" * 65)
    print("   SMARTLOAN AI - COMPREHENSIVE VERIFICATION TEST SUITE   ")
    print("=" * 65)

    # 1. Initialize Database
    print("\n[STEP 1] Testing Database Initialization & Seeding...")
    init_db()
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database.db'))
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    lenders_count = conn.execute("SELECT COUNT(*) FROM lenders").fetchone()[0]
    conn.close()
    print(f"  ✔ Users in database:   {users_count} (admin, borrower, newbie)")
    print(f"  ✔ Lenders in database: {lenders_count} products configured")
    assert users_count >= 3, "Users should be seeded!"
    assert lenders_count >= 8, "Lenders should be seeded!"

    # 2. Warm up ML Pipeline & verify model
    print("\n[STEP 2] Verifying Machine Learning Pipeline (Phase 2)...")
    ml_model = get_or_train_ml_model()
    assert ml_model is not None, "ML model should be loaded or trained successfully!"
    model_path = os.path.join(os.path.dirname(__file__), 'loan_classifier.pkl')
    assert os.path.exists(model_path), "loan_classifier.pkl should exist on disk!"
    print(f"  ✔ Machine Learning Model pipeline loaded from: {model_path}")

    # 3. Test EMI Calculations
    print("\n[STEP 3] Testing Financial EMI Calculation Mathematics...")
    calc_emi = calculate_emi(500000, 9.5, 5)
    expected_emi = 10500.95
    diff = abs(calc_emi - expected_emi)
    print(f"  ✔ 5 Lakhs @ 9.5% for 5 Yrs -> Calculated: ₹{calc_emi}, Expected: ₹{expected_emi} (Diff: {diff:.4f})")
    assert diff < 1.0, "EMI calculation deviation too high!"

    # 4. Test AI Dual Engine (Rule, ML, Ensemble)
    print("\n[STEP 4] Testing Dual Decision Engine (Rule vs ML vs Ensemble)...")
    
    # Test Prime applicant
    prime_offers_ens = evaluate_loan_offers(
        income=60000, existing_emis=5000, credit_score=750,
        loan_amount=300000, tenure_years=3, loan_type='Personal',
        employment_type='Salaried', engine_mode='ensemble'
    )
    prime_offers_rule = evaluate_loan_offers(
        income=60000, existing_emis=5000, credit_score=750,
        loan_amount=300000, tenure_years=3, loan_type='Personal',
        employment_type='Salaried', engine_mode='rule'
    )
    prime_offers_ml = evaluate_loan_offers(
        income=60000, existing_emis=5000, credit_score=750,
        loan_amount=300000, tenure_years=3, loan_type='Personal',
        employment_type='Salaried', engine_mode='ml'
    )

    top_ens = prime_offers_ens[0]
    top_rule = prime_offers_rule[0]
    top_ml = prime_offers_ml[0]

    print(f"  ✔ Top Product: {top_ens['loan_name']}")
    print(f"    - Phase 1 Rule Probability: {top_rule['approval_probability']}%")
    print(f"    - Phase 2 ML Probability:   {top_ml['approval_probability']}%")
    print(f"    - Blended Ensemble Score:   {top_ens['approval_probability']}%")
    print(f"    - Monthly EMI:              ₹{top_ens['monthly_emi']}")
    print(f"    - Net Disbursed Amount:     ₹{top_ens['net_disbursement']}")
    print(f"    - Factors:                  {top_ens['factors']}")

    assert top_ens['is_eligible'] == True, "Prime borrower should be eligible"
    assert top_ens['approval_probability'] >= 75, "Approval probability for prime borrower should be high"
    assert 'net_disbursement' in top_ens, "Net disbursement should be calculated"

    # 5. Test Rejection Checks (Low CIBIL)
    print("\n[STEP 5] Testing Rejection Underwriting Policy (Low CIBIL)...")
    low_cibil_offers = evaluate_loan_offers(
        income=80000, existing_emis=0, credit_score=520,
        loan_amount=200000, tenure_years=2, loan_type='Personal',
        employment_type='Salaried'
    )
    hdfc_offer = next((o for o in low_cibil_offers if 'HDFC' in o['lender_name']), None)
    if hdfc_offer:
        assert hdfc_offer['is_eligible'] == False, "HDFC Personal should reject CIBIL 520"
        print(f"  ✔ HDFC Policy Rejection Flagged: {hdfc_offer['rejection_reasons']}")

    # 6. Test Flask Client Endpoints
    print("\n[STEP 6] Testing REST Endpoints via Test Client...")
    client = app.test_client()

    # Test /api/loans/search
    res = client.post('/api/loans/search', json={
        'income': 50000,
        'existing_emis': 3000,
        'credit_score': 740,
        'loan_amount': 400000,
        'tenure_years': 4,
        'loan_type': 'Personal',
        'employment_type': 'Salaried',
        'engine_mode': 'ensemble'
    })
    assert res.status_code == 200, "Search endpoint failed"
    data = res.get_json()
    assert 'offers' in data and len(data['offers']) > 0, "Search should return offers"
    print("  ✔ /api/loans/search (200 OK) -> Offers returned successfully")

    # Test /api/cibil/optimize
    res_cibil = client.post('/api/cibil/optimize', json={
        'current_score': 650,
        'actions': ['reduce_utilization', 'clear_overdue']
    })
    assert res_cibil.status_code == 200, "CIBIL optimize endpoint failed"
    data_cibil = res_cibil.get_json()
    print(f"  ✔ /api/cibil/optimize (200 OK) -> Current: {data_cibil['current_score']}, Projected: {data_cibil['projected_score']} (+{data_cibil['points_gain']} pts)")
    assert data_cibil['projected_score'] > 650, "Score should increase"

    # Test /api/emi/optimize
    res_emi = client.post('/api/emi/optimize', json={
        'loan_amount': 500000,
        'interest_rate': 9.5,
        'target_budget': 13000
    })
    assert res_emi.status_code == 200, "EMI optimize endpoint failed"
    data_emi = res_emi.get_json()
    print(f"  ✔ /api/emi/optimize (200 OK) -> Recommended Tenure: {data_emi['recommended_tenure_years']} Yrs, EMI: ₹{data_emi['recommended_monthly_emi']}")
    assert data_emi['recommended_monthly_emi'] <= 13000, "Recommended EMI should stay within target budget"

    # Test /api/coach/chat in 5 languages
    print("\n[STEP 7] Testing Multilingual AI Financial Coach...")
    langs = ['en', 'hi', 'mr', 'gu', 'ta']
    for lang in langs:
        res_coach = client.post('/api/coach/chat', json={
            'message': 'cibil score',
            'language': lang
        })
        assert res_coach.status_code == 200
        coach_reply = res_coach.get_json()['reply']
        assert len(coach_reply) > 20, f"Coach reply too short for {lang}"
        print(f"  ✔ [{lang.upper()}] Coach Reply: {coach_reply[:60]}...")

    print("\n" + "=" * 65)
    print("   ALL TESTS PASSED! SMARTLOAN AI PLATFORM FULLY VERIFIED.   ")
    print("=" * 65)

if __name__ == '__main__':
    run_suite()
