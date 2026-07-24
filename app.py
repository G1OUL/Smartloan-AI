import sqlite3
import os
import math
from flask import Flask, request, jsonify, session, render_template, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = os.urandom(24)
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
# Helper: calculate EMI
def calculate_emi(principal, annual_rate, tenure_years):
    r = (annual_rate / 12) / 100
    n = tenure_years * 12
    if r == 0:
        return principal / n
    emi = principal * r * (math.pow(1 + r, n)) / (math.pow(1 + r, n) - 1)
    return round(emi, 2)
# AI rule engine to evaluate loans
def evaluate_loan_offers(income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type):
    conn = get_db_connection()
    # Fetch all lenders matching the loan type
    lenders = conn.execute("SELECT * FROM lenders WHERE loan_type = ?", (loan_type,)).fetchall()
    conn.close()
    offers = []
    
    # Base approval probability based on Credit Score (CIBIL)
    if credit_score < 500:
        base_prob = 10
    elif credit_score < 600:
        base_prob = 35
    elif credit_score < 650:
        base_prob = 55
    elif credit_score < 700:
        base_prob = 75
    elif credit_score < 750:
        base_prob = 88
    elif credit_score < 800:
        base_prob = 95
    else:
        base_prob = 98
    for lender in lenders:
        lender_dict = dict(lender)
        rejection_reasons = []
        is_eligible = True
        
        # Rule 1: Credit Score Eligibility
        if credit_score < lender_dict['min_credit_score']:
            is_eligible = False
            rejection_reasons.append(f"Credit score {credit_score} is below the lender's minimum of {lender_dict['min_credit_score']}.")
        # Rule 2: Minimum Income Eligibility
        # (For Education loans, we check co-borrower income which is entered as 'income' in the form)
        if income < lender_dict['min_income']:
            is_eligible = False
            rejection_reasons.append(f"Monthly income ₹{income:,.2f} is below the lender's minimum of ₹{lender_dict['min_income']:,.2f}.")
        # Rule 3: Tenure bounds check
        if tenure_years < lender_dict['min_tenure_years'] or tenure_years > lender_dict['max_tenure_years']:
            is_eligible = False
            rejection_reasons.append(f"Requested tenure {tenure_years} years is outside allowed range of {lender_dict['min_tenure_years']}-{lender_dict['max_tenure_years']} years.")
        # Calculate EMI & DTI
        emi = calculate_emi(loan_amount, lender_dict['interest_rate'], tenure_years)
        total_monthly_obligations = existing_emis + emi
        dti = total_monthly_obligations / income if income > 0 else 1.0
        # Rule 4: DTI Check
        if dti > lender_dict['max_dti']:
            is_eligible = False
            rejection_reasons.append(f"Estimated Debt-To-Income ratio ({dti*100:.1f}%) exceeds lender's max limit of {lender_dict['max_dti']*100:.1f}%.")
        # Rule 5: Employment restrictions
        if loan_type == 'Business' and employment_type == 'Unemployed':
            is_eligible = False
            rejection_reasons.append("Business loans require active business registration and are not available to unemployed applicants.")
        elif loan_type == 'Personal' and employment_type == 'Unemployed':
            is_eligible = False
            rejection_reasons.append("Personal loans require stable employment or salary and are not available to unemployed applicants.")
        # Calculate probability if eligible
        if is_eligible:
            prob = base_prob
            
            # Apply DTI adjustments
            if dti > 0.45:
                prob -= 20
            elif dti > 0.35:
                prob -= 10
            
            # Apply Employment adjustments
            if employment_type == 'Self-Employed':
                prob -= 5  # slightly higher risk perception
            elif employment_type == 'Unemployed' and loan_type == 'Education':
                # Allowed, but depends heavily on co-borrower credit profile (assumed represented by credit_score)
                prob -= 10
                
            # Clamp probability between 5% and 99%
            prob = max(5, min(99, prob))
        else:
            prob = 0
        # Calculation of Costs
        tenure_months = tenure_years * 12
        total_interest = round((emi * tenure_months) - loan_amount, 2)
        processing_fee = round((loan_amount * lender_dict['processing_fee_pct'] / 100) + lender_dict['flat_processing_fee'], 2)
        insurance_cost = round(loan_amount * lender_dict['insurance_premium_pct'] / 100, 2)
        total_cost = round(loan_amount + total_interest + processing_fee + insurance_cost, 2)
        # Generate recommendation commentary / advice
        advice = []
        if prob >= 85:
            advice.append("Highly Recommended: You meet or exceed all eligibility criteria, offering you an excellent chance of securing this loan.")
        elif prob >= 60:
            advice.append("Good Fit: You are eligible, though your DTI or Credit Score is close to the threshold. Application approval is likely.")
        elif is_eligible:
            advice.append("Moderate Fit: Low approval probability. Consider increasing your credit score or extending tenure to reduce EMI and DTI.")
        else:
            advice.append("Not Eligible: You currently do not meet the minimum criteria for this specific product.")
        if lender_dict['prepayment_penalty_pct'] == 0:
            advice.append("Flexibility: This loan features zero prepayment penalty charges, allowing you to pay it off early at no extra cost.")
        if lender_dict['processing_fee_pct'] == 0 and lender_dict['flat_processing_fee'] == 0:
            advice.append("Savings: Zero processing fees are charged upfront for this loan product.")
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
            'total_cost': total_cost,
            'approval_probability': prob,
            'is_eligible': is_eligible,
            'rejection_reasons': rejection_reasons,
            'required_docs': [doc.strip() for doc in lender_dict['required_docs'].split(';') if doc.strip()],
            'advice_commentary': " ".join(advice)
        })
    # Sort: Eligible first, then by high approval probability, then by lowest total cost
    offers.sort(key=lambda x: (not x['is_eligible'], -x['approval_probability'], x['total_cost']))
    return offers
# Serve single-page dashboard
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
    user_type = data.get('user_type', 'registered') # registered, first_time
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
    user = conn.execute("SELECT id, username, email, user_type FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    if user:
        return jsonify({'user': dict(user)})
    return jsonify({'user': None})
# Recommendations API
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
    except ValueError:
        return jsonify({'error': 'Invalid numerical values provided'}), 400
    # Business Validation
    if loan_amount <= 0 or tenure_years <= 0 or income <= 0:
        return jsonify({'error': 'Values must be greater than zero'}), 400
    offers = evaluate_loan_offers(income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type)
    # Save to history if logged in
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        # Save application
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO applications (user_id, income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, income, existing_emis, credit_score, loan_amount, tenure_years, loan_type, employment_type))
        app_id = cursor.lastrowid
        # Save top 3 eligible offers to history
        eligible_offers = [o for o in offers if o['is_eligible']][:3]
        for offer in eligible_offers:
            cursor.execute('''
                INSERT INTO saved_offers (user_id, application_id, lender_name, loan_name, loan_type, interest_rate, monthly_emi, total_interest, total_cost, approval_probability)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, app_id, offer['lender_name'], offer['loan_name'], offer['loan_type'], offer['interest_rate'], offer['monthly_emi'], offer['total_interest'], offer['total_cost'], offer['approval_probability']))
        
        conn.commit()
        conn.close()
    return jsonify({
        'offers': offers,
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
        # Fetch saved offers for this application
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
            return jsonify({'error': 'Invalid numerical inputs'}), 400
        if not name or not loan_name or not loan_type:
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
@app.route('/api/admin/lenders/<int:lender_id>', methods=['PUT', 'DELETE'])
def admin_modify_lender(lender_id):
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized. Admin access required.'}), 403
    conn = get_db_connection()
    # Check if exists
    lender = conn.execute("SELECT * FROM lenders WHERE id = ?", (lender_id,)).fetchone()
    if not lender:
        conn.close()
        return jsonify({'error': 'Lender product not found'}), 404
    if request.method == 'DELETE':
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
            return jsonify({'error': 'Invalid numerical inputs'}), 400
        if not name or not loan_name or not loan_type:
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
    # Loan applications by type for charts
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
        if new_type not in ['guest', 'registered', 'first_time', 'admin']:
            conn.close()
            return jsonify({'error': 'Invalid user type'}), 400
        conn.execute("UPDATE users SET user_type = ? WHERE id = ?", (new_type, user_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User type updated successfully.'})
if __name__ == '__main__':
    app.run(debug=True, port=5000)
