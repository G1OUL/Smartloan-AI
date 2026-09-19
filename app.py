import sqlite3
import os
import math
import pandas as pd
import numpy as np
import joblib
from flask import Flask, request, jsonify, session, render_template, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'loan_classifier.pkl')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Helper: calculate EMI
def calculate_emi(principal, annual_rate, tenure_years):
    r = (annual_rate / 12) / 100
    n = tenure_years * 12
    if r == 0:
        return round(principal / n, 2)
    emi = principal * r * (math.pow(1 + r, n)) / (math.pow(1 + r, n) - 1)
    return round(emi, 2)


# --- Phase 2: ML Model Management ---
_cached_ml_model = None


def get_or_train_ml_model():
    global _cached_ml_model
    if _cached_ml_model is not None:
        return _cached_ml_model

    if os.path.exists(MODEL_PATH):
        try:
            _cached_ml_model = joblib.load(MODEL_PATH)
            return _cached_ml_model
        except Exception as e:
            print(f"Warning: Failed to load saved ML model: {e}. Retraining...")

    try:
        from generate_dataset import generate_loan_dataset
        from clean_dataset import clean_loan_dataset
        from train_model import train_loan_model

        raw_csv = os.path.join(os.path.dirname(__file__), 'loan_data_raw.csv')
        clean_csv = os.path.join(os.path.dirname(__file__), 'loan_data_clean.csv')

        if not os.path.exists(clean_csv):
            if not os.path.exists(raw_csv):
                generate_loan_dataset(raw_csv, num_records=3000)
            clean_loan_dataset(raw_csv, clean_csv)

        train_loan_model(clean_csv, MODEL_PATH)
        _cached_ml_model = joblib.load(MODEL_PATH)
        return _cached_ml_model
    except Exception as ex:
        print(f"ML Pipeline Initialization Notice: {ex}")
        return None


# Dual-Engine: Phase 1 (Rule-based) & Phase 2 (ML Random Forest
def evaluate_loan_offers(income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type, engine_mode='ensemble'):
    conn = get_db_connection()
    lenders = conn.execute("SELECT * FROM lenders WHERE loan_type = ?", (loan_type,)).fetchall()
    conn.close()

    offers = []

    # Phase 1: Base Rule-based Probability via CIBIL & DTI
    if credit_score < 500:
        base_rule_prob = 10
    elif credit_score < 600:
        base_rule_prob = 35
    elif credit_score < 650:
        base_rule_prob = 55
    elif credit_score < 700:
        base_rule_prob = 75
    elif credit_score < 750:
        base_rule_prob = 88
    elif credit_score < 800:
        base_rule_prob = 95
    else:
        base_rule_prob = 98

    # Phase 2: Predict using Scikit-Learn Model if available
    ml_model = get_or_train_ml_model()
    raw_ml_prob = None
    if ml_model is not None:
        try:
            df_input = pd.DataFrame([{ 
                'income': float(income),
                'existing_emis': float(existing_emis),
                'credit_score': int(credit_score),
                'loan_amount': float(loan_amount),
                'tenure_years': int(tenure_years),
                'loan_type': str(loan_type),
                'employment_type': str(employment_type)
            }])
            proba_arr = ml_model.predict_proba(df_input)
            raw_ml_prob = round(float(proba_arr[0][1]) * 100, 1)
        except Exception as e:
            print(f"ML Inference fallback: {e}")
            raw_ml_prob = None

    for lender in lenders:
        lender_dict = dict(lender)
        rejection_reasons = []
        is_eligible = True

        # Rule 1: Credit Score Eligibility
        if credit_score < lender_dict['min_credit_score']:
            is_eligible = False
            rejection_reasons.append(f"Credit score {credit_score} is below lender minimum of {lender_dict['min_credit_score']}.")

        # Rule 2: Minimum Income Eligibility
        if income < lender_dict['min_income']:
            is_eligible = False
            rejection_reasons.append(f"Monthly income ₹{income:,.2f} is below lender minimum of ₹{lender_dict['min_income']:,.2f}.")

        # Rule 3: Tenure bounds check
        if tenure_years < lender_dict['min_tenure_years'] or tenure_years > lender_dict['max_tenure_years']:
            is_eligible = False
            rejection_reasons.append(f"Requested tenure {tenure_years} yrs is outside allowed range of {lender_dict['min_tenure_years']}-{lender_dict['max_tenure_years']} yrs.")

        # Calculate EMI & DTI
        emi = calculate_emi(loan_amount, lender_dict['interest_rate'], tenure_years)
        total_monthly_obligations = existing_emis + emi
        dti = total_monthly_obligations / income if income > 0 else 1.0

        # Rule 4: DTI Check
        if dti > lender_dict['max_dti']:
            is_eligible = False
            rejection_reasons.append(f"Estimated Debt-To-Income ({dti*100:.1f}%) exceeds lender's max threshold of {lender_dict['max_dti']*100:.1f}%.")

        # Rule 5: Employment restrictions
        if loan_type == 'Business' and employment_type == 'Unemployed':
            is_eligible = False
            rejection_reasons.append("Business loans require an active operational enterprise or business registration.")
        elif loan_type == 'Personal' and employment_type == 'Unemployed':
            is_eligible = False
            rejection_reasons.append("Personal loans require verified steady salary or self-employment income.")

        # Phase 1: Calculate Rule Score
        if is_eligible:
            r_prob = base_rule_prob
            if dti > 0.45:
                r_prob -= 20
            elif dti > 0.35:
                r_prob -= 10

            if employment_type == 'Self-Employed':
                r_prob -= 5
            elif employment_type == 'Unemployed' and loan_type == 'Education':
                r_prob -= 10

            rule_prob = max(5, min(99, r_prob))
        else:
            rule_prob = 0

        # Phase 2: Calculate ML Score for this lender
        if raw_ml_prob is not None:
            if not is_eligible:
                # Disqualified by lender policy
                ml_prob = min(15, round(raw_ml_prob * 0.15, 1))
            else:
                # Calibrate ML prediction against specific lender interest and DTI
                lender_adjustment = (12.0 - lender_dict['interest_rate']) * 1.5
                ml_prob = round(max(5, min(99, raw_ml_prob + lender_adjustment)), 1)
        else:
            ml_prob = rule_prob

        # Select Score based on Engine Mode
        if engine_mode == 'rule':
            final_prob = rule_prob
        elif engine_mode == 'ml':
            final_prob = ml_prob if is_eligible else 0
        else:  # Ensemble
            if is_eligible:
                final_prob = round(0.5 * rule_prob + 0.5 * ml_prob, 1)
            else:
                final_prob = 0

        # Calculation of Costs & Transparency Breakdown
        tenure_months = tenure_years * 12
        total_interest = round((emi * tenure_months) - loan_amount, 2)
        processing_fee = round((loan_amount * lender_dict['processing_fee_pct'] / 100) + lender_dict['flat_processing_fee'], 2)
        insurance_cost = round(loan_amount * lender_dict['insurance_premium_pct'] / 100, 2)
        total_cost = round(loan_amount + total_interest + processing_fee + insurance_cost, 2)
        net_disbursement = round(loan_amount - processing_fee - insurance_cost, 2)

        # Factor contributions for transparency
        factors = {
            'cibil_factor': f"Score {credit_score} (" + ("Excellent" if credit_score >= 750 else "Average" if credit_score >= 650 else "High Risk") + ")",
            'dti_factor': f"DTI {dti*100:.1f}% (" + ("Healthy" if dti <= 0.4 else "High" if dti <= 0.5 else "Critical") + ")",
            'fee_factor': f"₹{processing_fee:,.0f} fee + ₹{insurance_cost:,.0f} ins",
            'prepayment_factor': "0% Penalty (High Flexibility)" if lender_dict['prepayment_penalty_pct'] == 0 else f"{lender_dict['prepayment_penalty_pct']}% Prepayment Fee"
        }

        # Advice commentary
        advice = []
        if final_prob >= 85:
            advice.append("Highly Recommended: Prime profile meeting all eligibility checks. Fastest approval path.")
        elif final_prob >= 60:
            advice.append("Good Fit: High approval odds. Ensure your 6-month bank statements show consistent balances.")
        elif is_eligible:
            advice.append("Moderate Fit: You meet minimum criteria, but consider reducing existing debts or extending tenure to lower DTI.")
        else:
            advice.append("Not Eligible: Does not satisfy lender policy. Review the rejection flags below.")

        if lender_dict['prepayment_penalty_pct'] == 0:
            advice.append("Flexibility: 0% prepayment penalty allows you to pay off debt early with zero charges.")
        if processing_fee == 0:
            advice.append("Savings: Zero upfront processing fees on this loan.")

        offers.append({
            'lender_id': lender_dict['id'],
            'lender_name': lender_dict['name'],
            'loan_name': lender_dict['name'] + " - " + lender_dict['loan_name'],
            'loan_type': lender_dict['loan_type'],
            'interest_rate': lender_dict['interest_rate'],
            'monthly_emi': emi,
            'total_interest': total_interest,
            'processing_fee': processing_fee,
            'insurance_cost': insurance_cost,
            'prepayment_penalty_pct': lender_dict['prepayment_penalty_pct'],
            'net_disbursement': net_disbursement,
            'total_cost': total_cost,
            'approval_probability': final_prob,
            'rule_probability': rule_prob,
            'ml_probability': ml_prob,
            'factors': factors,
            'is_eligible': is_eligible,
            'rejection_reasons': rejection_reasons,
            'required_docs': [doc.strip() for doc in lender_dict['required_docs'].split(';') if doc.strip()],
            'advice_commentary': " ".join(advice)
        })

    # Sort: Eligible first, highest approval probability, then lowest total cost
    offers.sort(key=lambda x: (not x['is_eligible'], -x['approval_probability'], x['total_cost']))
    return offers


# Routes
@app.route('/')
def index():
    return render_template('index.html')


# Authentication APIs
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    user_type = data.get('user_type', 'registered')

    if not username or not password or not email:
        return jsonify({'error': 'Please fill in all details'}), 400

    if user_type not in ['registered', 'first_time']:
        user_type = 'registered'

    conn = get_db_connection()
    try:
        password_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash, email, user_type) VALUES (?, ?, ?, ?)",
            (username, password_hash, email, user_type)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or Email already exists'}), 400
    finally:
        conn.close()

    return jsonify({'message': 'Registration successful. You can log in now!'})


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Please provide username and password'}), 400

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['user_type'] = user['user_type']
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'user_type': user['user_type']
            }
        })

    return jsonify({'error': 'Invalid username or password'}), 401


@app.route('/api/auth/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/auth/me', methods=['GET'])
def me():
    if 'user_id' not in session:
        return jsonify({'user': None})

    conn = get_db_connection()
    user = conn.execute("SELECT id, username, email, user_type, created_at FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()

    if user:
        return jsonify({'user': dict(user)})
    return jsonify({'user': None})


@app.route('/api/auth/profile', methods=['PUT'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    email = data.get('email')
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    # If updating password
    if new_password:
        if not current_password or not check_password_hash(user['password_hash'], current_password):
            conn.close()
            return jsonify({'error': 'Current password is incorrect'}), 400
        if len(new_password) < 4:
            conn.close()
            return jsonify({'error': 'New password must be at least 4 characters'}), 400
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), session['user_id']))

    # If updating email
    if email and email != user['email']:
        try:
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, session['user_id']))
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Email address is already in use'}), 400

    conn.commit()
    conn.close()
    return jsonify({'message': 'Profile updated successfully'})


# Recommendations & Search API
@app.route('/api/loans/search', methods=['POST'])
def search_loans():
    data = request.get_json() or {}
    try:
        income = float(data.get('income', 0))
        existing_emis = float(data.get('existing_emis', 0))
        credit_score = int(data.get('credit_score', 300))
        loan_amount = float(data.get('loan_amount', 0))
        tenure_years = int(data.get('tenure_years', 1))
        loan_type = data.get('loan_type', 'Personal')
        employment_type = data.get('employment_type', 'Salaried')
        engine_mode = data.get('engine_mode', 'ensemble')  # 'ensemble', 'rule', 'ml'
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numerical values provided'}), 400

    if loan_amount <= 0 or tenure_years <= 0 or income <= 0:
        return jsonify({'error': 'Values must be greater than zero'}), 400

    offers = evaluate_loan_offers(income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type, engine_mode)

    # Save to history if logged in
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO applications (user_id, income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type))
        app_id = cursor.lastrowid

        eligible_offers = [o for o in offers if o['is_eligible']][:3]
        for offer in eligible_offers:
            cursor.execute('''
                INSERT INTO saved_offers (
                    user_id, application_id, lender_name, loan_name, loan_type,
                    interest_rate, monthly_emi, total_interest, total_cost, approval_probability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                app_id,
                offer['lender_name'],
                offer['loan_name'],
                offer['loan_type'],
                offer['interest_rate'],
                offer['monthly_emi'],
                offer['total_interest'],
                offer['total_cost'],
                offer['approval_probability']
            ))

        conn.commit()
        conn.close()

    return jsonify({
        'offers': offers,
        'engine_mode': engine_mode,
        'summary': {
            'income': income,
            'existing_emis': existing_emis,
            'credit_score': credit_score,
            'loan_amount': loan_amount,
            'tenure_years': tenure_years,
            'loan_type': loan_type,
            'employment_type': employment_type
        }
    })


# CIBIL Score Simulator API
@app.route('/api/cibil/optimize', methods=['POST'])
def optimize_cibil():
    data = request.get_json() or {}
    try:
        current_score = int(data.get('current_score', 650))
    except (ValueError, TypeError):
        current_score = 650

    actions = data.get('actions', [])
    # Action impact weights
    action_weights = {
        'reduce_utilization': {'pts': 35, 'title': 'Keep Credit Card Utilization Under 30%', 'timeline': '30-45 Days'},
        'clear_overdue': {'pts': 45, 'title': 'Clear All Overdue / DPD Accounts', 'timeline': '45-60 Days'},
        'auto_debit': {'pts': 20, 'title': 'Set Up Auto-Debit for 100% On-Time Record', 'timeline': '60-90 Days'},
        'avoid_inquiries': {'pts': 15, 'title': 'Avoid Applying to Multiple Lenders Directly', 'timeline': 'Immediate'},
        'credit_mix': {'pts': 10, 'title': 'Maintain Balanced Credit Mix (Secured & Unsecured)', 'timeline': '90+ Days'}
    }

    total_boost = 0
    selected_tips = []
    for action in actions:
        if action in action_weights:
            total_boost += action_weights[action]['pts']
            selected_tips.append(action_weights[action])

    projected_score = min(900, current_score + total_boost)

    # Estimate approval probability before and after
    def score_to_prob(s):
        if s < 600:
            return 25
        if s < 650:
            return 50
        if s < 700:
            return 72
        if s < 750:
            return 85
        return 95

    return jsonify({
        'current_score': current_score,
        'projected_score': projected_score,
        'points_gain': total_boost,
        'current_approval_odds': score_to_prob(current_score),
        'projected_approval_odds': score_to_prob(projected_score),
        'estimated_rate_discount': "0.5% - 1.5% lower p.a." if projected_score >= 750 and current_score < 750 else "Best market tier",
        'actions_applied': selected_tips
    })


# EMI Optimization API
@app.route('/api/emi/optimize', methods=['POST'])
def optimize_emi():
    data = request.get_json() or {}
    try:
        loan_amount = float(data.get('loan_amount', 500000))
        rate = float(data.get('interest_rate', 9.5))
        target_budget = float(data.get('target_budget', 12000))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numerical inputs'}), 400

    # Test tenures from 1 to 30 years to find optimal tenure matching budget
    best_tenure = None
    best_emi = None
    tenure_options = []

    for t in range(1, 31):
        emi = calculate_emi(loan_amount, rate, t)
        total_int = round((emi * t * 12) - loan_amount, 2)
        tenure_options.append({'tenure_years': t, 'emi': emi, 'total_interest': total_int})
        if emi <= target_budget and best_tenure is None:
            best_tenure = t
            best_emi = emi

    if best_tenure is None:
        best_tenure = 30
        best_emi = tenure_options[-1]['emi']

    # Standard 5-year comparison
    standard_5yr_emi = calculate_emi(loan_amount, rate, 5)
    standard_5yr_interest = round((standard_5yr_emi * 60) - loan_amount, 2)
    optimal_interest = round((best_emi * best_tenure * 12) - loan_amount, 2)
    savings = round(max(0, standard_5yr_interest - optimal_interest), 2)

    return jsonify({
        'loan_amount': loan_amount,
        'interest_rate': rate,
        'target_budget': target_budget,
        'recommended_tenure_years': best_tenure,
        'recommended_monthly_emi': best_emi,
        'total_interest': optimal_interest,
        'interest_saved_vs_longer_tenure': savings,
        'tenure_options': tenure_options[:15]
    })


# AI Financial Coach API (Conversational Advisory)
@app.route('/api/coach/chat', methods=['POST'])
def coach_chat():
    data = request.get_json() or {}
    message = (data.get('message') or '').strip().lower()
    lang = data.get('language', 'en')

    # Intelligent intent matching
    reply_en = ""
    reply_hi = ""
    reply_mr = ""
    reply_gu = ""
    reply_ta = ""

    if any(k in message for k in ['cibil', 'credit score', 'score', 'cibil score']):
        reply_en = "Your CIBIL score (300-900) determines your loan eligibility and interest rates. Above 750 gives you prime rates and fastest approvals. To boost your score: keep credit card utilization below 30%, pay EMIs on time, avoid too many credit inquiries, and maintain a healthy credit mix."
        reply_hi = "आपका सिबिल स्कोर (300-900) आपकी ऋण पात्रता और ब्याज दर तय करता है। 750 से ऊपर होने पर आपको प्राइम दरें और तेज़ स्वीकृति मिलती है। स्कोर बढ़ाने के लिए: क्रेडिट कार्ड उपयोग 30% से कम रखें, EMI समय पर चुकाएं, बहुत ज़्यादा inquiry से बचें, और संतुलित क्रेडिट मिक्स बनाए रखें।"
        reply_mr = "तुमचा सिबिल स्कोअर (300-900) तुमची कर्ज पात्रता आणि व्याजदर ठरवतो. 750 पेक्षा जास्त असल्यास तुम्हाला प्राइम दर आणि जलद मंजुरी मिळते. स्कोअर वाढवण्यासाठी: क्रेडिट कार्ड वापर 30% पेक्षा कमी ठेवा, EMI वेळेवर भरा, जास्त inquiry टाळा आणि संतुलित क्रेडिट मिक्स ठेवा."
        reply_gu = "તમારો CIBIL સ્કોર (300-900) તમારી લોન પાત્રતા અને વ્યાજ દર નક્કી કરે છે. 750 થી ઉપર હોય તો તમને પ્રાઇમ રેટ અને ઝડપી મંજૂરી મળે છે. સ્કોર વધારવા માટે: ક્રેડિટ કાર્ડ ઉપયોગ 30%થી નીચે રાખો, EMI સમય પર ચૂકવો, વધુ enquiryથી બચો અને સંતુલિત ક્રેડિટ મિક્સ રાખો."
        reply_ta = "உங்கள் CIBIL மதிப்பெண் (300-900) உங்கள் கடன் தகுதி மற்றும் வட்டி விகிதத்தை தீர்மானிக்கிறது. 750-க்கு மேல் இருந்தால் பிரைம் வட்டி மற்றும் வேகமான ஒப்புதல் கிடைக்கும். மதிப்பெண்ணை உயர்த்த: கிரெடிட் கார்டு பயன்பாட்டை 30%க்கு கீழ் வைத்திருங்கள், EMIஐ சரியான நேரத்தில் செலுத்துங்கள், அதிக enquiryகளைக் தவிர்க்கவும், நல்ல கிரெடிட் கலவையை பராமரிக்கவும்."

    elif any(k in message for k in ['dti', 'debt to income', 'ratio', 'existing']):
        reply_en = "Debt-to-Income (DTI) is the percentage of your monthly income used to pay EMIs (existing + new loan). Banks strictly look for DTI under 40-50%. If your DTI is too high, you can reduce it by increasing income, paying down existing EMIs, or choosing a longer tenure."
        reply_hi = "डेट-टू-इनकम (DTI) अनुपात यह दर्शाता है कि आपकी मासिक आय का कितना हिस्सा मौजूदा और नए EMI में जाता है। बैंक आमतौर पर 40-50% से नीचे DTI देखना पसंद करते हैं। अगर DTI अधिक है, तो आय बढ़ाएं, पुराने EMI घटाएं, या लंबी अवधि चुनें।"
        reply_mr = "डेट-टू-इन्कम (DTI) रेश्यो दर्शवतो की तुमच्या मासिक उत्पन्नाचा किती भाग अस्तित्वातील आणि नवीन EMI मध्ये जातो. बँका सामान्यतः 40-50% पेक्षा कमी DTI पाहतात. DTI जास्त असल्यास उत्पन्न वाढवा, जुने EMI कमी करा किंवा जास्त कालावधी निवडा."
        reply_gu = "ડેબ્ટ-ટુ-ઇનકમ (DTI) રેશિયો બતાવે છે કે તમારી માસિક આવકનો કેટલો ભાગ હાલના અને નવા EMIમાં જતો હોય છે. બેંકો સામાન્ય રીતે 40-50% થી નીચેનો DTI પસંદ કરે છે. DTI વધુ હોય તો આવક વધારें, હાલના EMI ઘટાડો અથવા લાંબી મુદત પસંદ કરો."
        reply_ta = "கடன்-வருமான விகிதம் (DTI) என்பது உங்கள் மாத வருமானத்தில் தற்போதைய மற்றும் புதிய EMIக்கு எவ்வளவு பங்கு செலவாகிறது என்பதைக் குறிக்கிறது. வங்கிகள் பொதுவாக 40-50%க்கு கீழ் உள்ள DTIஐ விரும்புகின்றனர். DTI அதிகமாக இருந்தால் வருமானத்தை அதிகரிக்கவும், தற்போதைய EMIகளை குறைக்கவும் அல்லது நீண்ட காலத்தை தேர்வு செய்யவும்."

    elif any(k in message for k in ['fee', 'hidden', 'cost', 'charge', 'processing', 'prepayment', 'foreclosure']):
        reply_en = "Never look only at the interest rate! Hidden costs include processing fees (0.5% - 2% + GST), mandatory insurance, and prepayment penalties (2% - 4% if closing early). Smart borrowers compare total cost of borrowing, not just monthly EMI."
        reply_hi = "सिर्फ ब्याज दर न देखें! छिपे हुए शुल्कों में प्रोसेसिंग फीस (0.5% - 2% + GST), अनिवार्य बीमा और प्रीपेमेंट पेनल्टी (जल्दी बंद करने पर 2% - 4%) शामिल होते हैं। स्मार्ट उधारकर्ता सिर्फ EMI नहीं, कुल ऋण लागत की तुलना करते हैं।"
        reply_mr = "केवळ व्याजदर पाहू नका! लपलेले शुल्क ज्यामध्ये प्रोसेसिंग फी (0.5% - 2% + GST), अनिवार्य विमा आणि प्रीपेमेंट पेनल्टी (जल्दी बंद केल्यावर 2% - 4%) समाविष्ट असतात. स्मार्ट उधारदार फक्त EMI नाही, एकूण कर्ज खर्चाची तुलना करतात."
        reply_gu = "માત્ર વ્યાજ દર જોશો નહીં! છૂપા ચાર્જીસમાં પ્રોસેસિંગ ફી (0.5% - 2% + GST), compulsory insurance, અને prepayment penalty (ઝૂકાવું બંધ કરાવામાં 2% - 4%) શામેલ છે. સ્માર્ટ उधારનાર ફક્ત EMI નહીં, કુલ લોન ખર્ચની સરખામણી કરે છે."
        reply_ta = "வட்டி விகிதத்தை மட்டும் பார்ப்பதை தவிர்க்கவும்! மறைமுக செலவுகளில் செயலாக்கக் கட்டணம் (0.5% - 2% + GST), கட்டாய காப்பீடு, மற்றும் முன்கூட்டியே செலுத்தும் அபராதம் (விரைவாக மூடும்போது 2% - 4%) அடங்கும். புத்திசாலித்தனமான கடன் வாங்குபவர்கள் மாத EMI மட்டும் பார்க்காமல் மொத்த கடன் செலவையும் ஒப்பிடுகின்றனர்."

    elif any(k in message for k in ['document', 'docs', 'paper', 'pan', 'aadhaar', 'digilocker', 'itr']):
        reply_en = "Standard required documents: 1) Identity & Address: PAN Card & Aadhaar (download instantly via DigiLocker), 2) Income: 3-month salary slips & 6-month bank statement (e-statement), 3) Employment proof and residence proof."
        reply_hi = "ज़रूरी दस्तावेज़: 1) पहचान: पैन और आधार (DigiLocker से तुरंत डाउनलोड), 2) आय-संबंधित: 3 महीने का सैलरी स्लिप और 6 महीने का बैंक स्टेटमेंट, 3) रोजगार और पता प्रमाण."
        reply_mr = "आवश्यक कागदपत्रे: 1) ओळख आणि पत्ता: पॅन कार्ड आणि आधार (DigiLocker वरून त्वरित डाउनलोड), 2) उत्पन्न: 3 महिन्यांचे सॅलरी स्लिप्स आणि 6 महिन्यांचे बँक स्टेटमेंट, 3) नोकरी आणि पत्ता पुरावा."
        reply_gu = "જરૂરી દસ્તાવેજો: 1) ઓળખ અને સરનામું: PAN Card અને Aadhaar (DigiLockerમાંથી ફટાફટ ડાઉનલોડ), 2) આવક: 3 મહિનાની સેલેરી સ્લિપ અને 6 મહિના bancaire સ્ટેટમેન્ટ, 3) નોકરી અને સરનામાનો પુરાવો."
        reply_ta = "தேவையான ஆவணங்கள்: 1) அடையாளம் மற்றும் முகவரி: பான் கார்டு மற்றும் ஆதார் (DigiLocker மூலம் உடனடியாக பதிவிறக்கம்), 2) வருமானம்: 3 மாத சம்பளச் சீட்டு மற்றும் 6 மாத வங்கி அறிக்கை, 3) வேலை மற்றும் முகவரி சான்றுகள்."

    elif any(k in message for k in ['first time', 'student', 'beginner', 'fresher', 'education']):
        reply_en = "Welcome! As a first-time applicant: 1) For Education loans up to ₹7.5 Lakhs under government CSIS schemes, collateral is often not required. 2) Add an earning parent as co-borrower if needed. 3) Keep your CIBIL clean and avoid multiple loan applications."
        reply_hi = "नमस्ते! पहली बार आवेदन करने वालों के लिए: 1) ₹7.5 लाख तक के शिक्षा ऋण पर सरकारी CSIS योजना के तहत अक्सर collateral नहीं चाहिए. 2) जरूरत पड़ने पर कमाने वाले माता-पिता को co-borrower बनाएं. 3) CIBIL साफ रखें और कई लोन applications से बचें."
        reply_mr = "स्वागत आहे! पहिल्यांदा कर्ज घेणाऱ्यांसाठी: 1) ₹7.5 लाखांपर्यंतचे शिक्षण कर्ज सरकारच्या CSIS योजनेत सहसा collateral आवश्यक नसते. 2) गरज पडल्यास कमावणाऱ्या पालकांना co-borrower बनवा. 3) CIBIL स्वच्छ ठेवा आणि अनेक लोन अर्ज टाळा."
        reply_gu = "સ્વાગત છે! પ્રથમ વખતના અરજીદારો માટે: 1) ₹7.5 લાખ સુધીની એજ્યુકેશન લોન પર સરકારની CSIS યોજનામાં ઘણીવાર collateral ની જરૂર નથી. 2) જરૂર હોય તો કમાવનાર માતા-પિતાને co-borrower બનાવો. 3) CIBIL સાફ રાખો અને ઘણી લોન અરજીઓ ટાળો."
        reply_ta = "வணக்கம்! முதல் முறை விண்ணப்பதாரர்களுக்கு: 1) ₹7.5 லட்சம் வரையிலான கல்விக் கடனில் அரசின் CSIS திட்டத்தின் கீழ் பெரும்பாலும் collateral தேவையில்லை. 2) தேவைப்பட்டால் சம்பாதிக்கும் பெற்றோரை co-borrower ஆக சேர்க்கவும். 3) CIBIL ஐ சுத்தமாக வைத்திருங்கள் மற்றும் பல கடன் விண்ணப்பங்களை தவிர்க்கவும்."

    else:
        reply_en = "I am your SmartLoan AI Financial Coach. Ask me about CIBIL score improvement, DTI ratios, hidden banking charges, required documents, or how to choose the right loan product for your profile."
        reply_hi = "मैं आपका स्मार्टलोन एआई वित्तीय सलाहकार हूँ। आप मुझसे CIBIL स्कोर में सुधार, DTI अनुपात, छिपे हुए बैंकिंग शुल्क, आवश्यक दस्तावेज़ या सही लोन का चुनाव पूछ सकते हैं।"
        reply_mr = "मी तुमचा SmartLoan AI फायनान्शियल कोच आहे. CIBIL स्कोअर सुधारणा, DTI रेश्यो, लपलेले बँकिंग शुल्क, आवश्यक कागदपत्रे किंवा योग्य कर्ज निवड याबद्दल मला विचारा."
        reply_gu = "હું તમારો SmartLoan AI ფინანს coach છું. CIBIL સ્કોર સુધારો, DTI રેશિયો, છૂપા બેંકિંગ ચાર્જીસ, જરૂરી દસ્તાવેજો અથવા તમારી પ્રોફાઇલ માટે યોગ્ય લોન પસંદ કરવા વિશે પૂછો."
        reply_ta = "நான் உங்கள் SmartLoan AI நிதி ஆலோசகர். CIBIL மதிப்பெண் மேம்பாடு, DTI விகிதம், மறைமுக வங்கி கட்டணங்கள், தேவையான ஆவணங்கள் அல்லது உங்கள் சுயவிவரத்திற்கான சரியான கடனை தேர்ந்தெடுப்பது பற்றி கேளுங்கள்."

    responses = {
        'en': reply_en,
        'hi': reply_hi,
        'mr': reply_mr,
        'gu': reply_gu,
        'ta': reply_ta
    }

    return jsonify({
        'reply': responses.get(lang, reply_en),
        'language': lang,
        'coach': 'SmartLoan AI Advisor'
    })


# History API
@app.route('/api/applications/history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    applications = conn.execute('''
        SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    history_data = []
    for app_row in applications:
        app_dict = dict(app_row)
        saved_offers = conn.execute('''
            SELECT * FROM saved_offers WHERE application_id = ?
        ''', (app_dict['id'],)).fetchall()
        app_dict['saved_offers'] = [dict(o) for o in saved_offers]
        history_data.append(app_dict)
    conn.close()
    return jsonify({'history': history_data})


# Admin APIs: Manage Lenders
@app.route('/api/admin/lenders', methods=['GET', 'POST'])
def admin_lenders():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized. Admin access required.'}), 403

    conn = get_db_connection()
    if request.method == 'GET':
        lenders = conn.execute("SELECT * FROM lenders").fetchall()
        conn.close()
        return jsonify({'lenders': [dict(l) for l in lenders]})

    elif request.method == 'POST':
        data = request.get_json() or {}
        try:
            name = data.get('name')
            loan_name = data.get('loan_name')
            loan_type = data.get('loan_type')
            min_credit_score = int(data.get('min_credit_score', 600))
            min_income = float(data.get('min_income', 0))
            max_dti = float(data.get('max_dti', 0.5))
            interest_rate = float(data.get('interest_rate', 10.0))
            processing_fee_pct = float(data.get('processing_fee_pct', 1.0))
            flat_processing_fee = float(data.get('flat_processing_fee', 0))
            insurance_premium_pct = float(data.get('insurance_premium_pct', 0.5))
            prepayment_penalty_pct = float(data.get('prepayment_penalty_pct', 0))
            min_tenure_years = int(data.get('min_tenure_years', 1))
            max_tenure_years = int(data.get('max_tenure_years', 5))
            required_docs = data.get('required_docs', 'PAN Card;Aadhaar Card')
        except ValueError:
            conn.close()
            return jsonify({'error': 'Invalid numerical inputs'}), 400

        if not name or not loan_name or not loan_type:
            conn.close()
            return jsonify({'error': 'Please fill all textual fields'}), 400

        conn.execute('''
            INSERT INTO lenders (
                name, loan_name, loan_type, min_credit_score, min_income, max_dti,
                interest_rate, processing_fee_pct, flat_processing_fee,
                insurance_premium_pct, prepayment_penalty_pct, min_tenure_years, max_tenure_years, required_docs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, loan_name, loan_type, min_credit_score, min_income, max_dti, interest_rate,
              processing_fee_pct, flat_processing_fee, insurance_premium_pct, prepayment_penalty_pct,
              min_tenure_years, max_tenure_years, required_docs))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Lender product added successfully.'})


@app.route('/api/admin/lenders/<int:lender_id>', methods=['GET', 'PUT', 'DELETE'])
def admin_modify_lender(lender_id):
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized. Admin access required.'}), 403

    conn = get_db_connection()
    lender = conn.execute("SELECT * FROM lenders WHERE id = ?", (lender_id,)).fetchone()
    if not lender:
        conn.close()
        return jsonify({'error': 'Lender product not found'}), 404

    if request.method == 'GET':
        conn.close()
        return jsonify({'lender': dict(lender)})

    elif request.method == 'DELETE':
        conn.execute("DELETE FROM lenders WHERE id = ?", (lender_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Lender product deleted successfully.'})

    elif request.method == 'PUT':
        data = request.get_json() or {}
        try:
            name = data.get('name')
            loan_name = data.get('loan_name')
            loan_type = data.get('loan_type')
            min_credit_score = int(data.get('min_credit_score'))
            min_income = float(data.get('min_income'))
            max_dti = float(data.get('max_dti'))
            interest_rate = float(data.get('interest_rate'))
            processing_fee_pct = float(data.get('processing_fee_pct'))
            flat_processing_fee = float(data.get('flat_processing_fee'))
            insurance_premium_pct = float(data.get('insurance_premium_pct'))
            prepayment_penalty_pct = float(data.get('prepayment_penalty_pct'))
            min_tenure_years = int(data.get('min_tenure_years'))
            max_tenure_years = int(data.get('max_tenure_years'))
            required_docs = data.get('required_docs')
        except (ValueError, TypeError):
            conn.close()
            return jsonify({'error': 'Invalid numerical inputs'}), 400

        if not name or not loan_name or not loan_type:
            conn.close()
            return jsonify({'error': 'Please fill all textual fields'}), 400

        conn.execute('''
            UPDATE lenders SET
                name=?, loan_name=?, loan_type=?, min_credit_score=?, min_income=?, max_dti=?,
                interest_rate=?, processing_fee_pct=?, flat_processing_fee=?,
                insurance_premium_pct=?, prepayment_penalty_pct=?, min_tenure_years=?, max_tenure_years=?, required_docs=?
            WHERE id=?
        ''', (name, loan_name, loan_type, min_credit_score, min_income, max_dti, interest_rate,
              processing_fee_pct, flat_processing_fee, insurance_premium_pct, prepayment_penalty_pct,
              min_tenure_years, max_tenure_years, required_docs, lender_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Lender product updated successfully.'})


# Admin API: Analytics
@app.route('/api/admin/analytics', methods=['GET'])
def admin_analytics():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE user_type != 'admin'").fetchone()[0]
    total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

    avg_metrics = conn.execute('''
        SELECT AVG(credit_score) as avg_cibil, AVG(loan_amount) as avg_amount, AVG(income) as avg_income 
        FROM applications
    ''').fetchone()

    popular_loan = conn.execute('''
        SELECT loan_type, COUNT(*) as cnt 
        FROM applications 
        GROUP BY loan_type 
        ORDER BY cnt DESC 
        LIMIT 1
    ''').fetchone()

    apps_by_type = conn.execute('''
        SELECT loan_type, COUNT(*) as cnt 
        FROM applications 
        GROUP BY loan_type
    ''').fetchall()
    conn.close()

    return jsonify({
        'total_users': total_users,
        'total_applications': total_apps,
        'avg_credit_score': round(avg_metrics['avg_cibil'] or 0, 1),
        'avg_loan_amount': round(avg_metrics['avg_amount'] or 0, 2),
        'avg_income': round(avg_metrics['avg_income'] or 0, 2),
        'popular_loan_type': popular_loan['loan_type'] if popular_loan else 'None',
        'distribution': {row['loan_type']: row['cnt'] for row in apps_by_type}
    })


# Admin API: Manage Users
@app.route('/api/admin/users', methods=['GET'])
def admin_users():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized. Admin access required.'}), 403

    conn = get_db_connection()
    users = conn.execute("SELECT id, username, email, user_type, created_at FROM users").fetchall()
    conn.close()
    return jsonify({'users': [dict(u) for u in users]})


@app.route('/api/admin/users/<int:user_id>', methods=['PUT', 'DELETE'])
def admin_modify_user(user_id):
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized. Admin access required.'}), 403

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    if request.method == 'DELETE':
        if user_id == session['user_id']:
            conn.close()
            return jsonify({'error': 'Cannot delete your own admin account'}), 400
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User deleted successfully.'})
    elif request.method == 'PUT':
        data = request.get_json() or {}
        new_type = data.get('user_type')
        new_email = data.get('email')
        new_password = data.get('new_password')

        if new_type and new_type not in ['guest', 'registered', 'first_time', 'admin']:
            conn.close()
            return jsonify({'error': 'Invalid user type'}), 400

        if new_type:
            conn.execute("UPDATE users SET user_type = ? WHERE id = ?", (new_type, user_id))
        if new_email:
            try:
                conn.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))
            except sqlite3.IntegrityError:
                conn.close()
                return jsonify({'error': 'Email address already in use'}), 400
        if new_password and len(new_password) >= 4:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), user_id))

        conn.commit()
        conn.close()
        return jsonify({'message': 'User profile updated successfully.'})


if __name__ == '__main__':
    # Initialize DB tables and seed data if missing
    from init_db import init_db
    init_db()
    # Warm up ML pipeline
    get_or_train_ml_model()
    app.run(debug=True, port=5000)
