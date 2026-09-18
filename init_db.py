import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(80) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        user_type VARCHAR(20) NOT NULL DEFAULT 'registered', -- guest, registered, first_time, admin
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create Lenders table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lenders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        loan_name VARCHAR(100) NOT NULL,
        loan_type VARCHAR(50) NOT NULL, -- Personal, Home, Education, Business
        min_credit_score INTEGER NOT NULL,
        min_income REAL NOT NULL,
        max_dti REAL NOT NULL,
        interest_rate REAL NOT NULL,
        processing_fee_pct REAL NOT NULL,
        flat_processing_fee REAL NOT NULL,
        insurance_premium_pct REAL NOT NULL,
        prepayment_penalty_pct REAL NOT NULL,
        min_tenure_years INTEGER NOT NULL,
        max_tenure_years INTEGER NOT NULL,
        required_docs TEXT NOT NULL
    )
    ''')

    # Create Applications table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        income REAL NOT NULL,
        existing_emis REAL NOT NULL,
        credit_score INTEGER NOT NULL,
        loan_amount REAL NOT NULL,
        tenure_years INTEGER NOT NULL,
        loan_type VARCHAR(50) NOT NULL,
        employment_type VARCHAR(50) NOT NULL, -- Salaried, Self-Employed, Unemployed
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create Saved Recommendations/History table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        application_id INTEGER,
        lender_name VARCHAR(100) NOT NULL,
        loan_name VARCHAR(100) NOT NULL,
        loan_type VARCHAR(50) NOT NULL,
        interest_rate REAL NOT NULL,
        monthly_emi REAL NOT NULL,
        total_interest REAL NOT NULL,
        total_cost REAL NOT NULL,
        approval_probability REAL NOT NULL,
        saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (application_id) REFERENCES applications (id)
    )
    ''')

    # Seed Users
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        users_to_seed = [
            ('admin', generate_password_hash('admin123'), 'admin@smartloan.ai', 'admin'),
            ('borrower', generate_password_hash('borrower123'), 'borrower@gmail.com', 'registered'),
            ('newbie', generate_password_hash('newbie123'), 'newbie@gmail.com', 'first_time')
        ]
        cursor.executemany("INSERT INTO users (username, password_hash, email, user_type) VALUES (?, ?, ?, ?)", users_to_seed)
        print("Users seeded successfully.")

    # Seed Lenders & Loan Products
    cursor.execute("SELECT COUNT(*) FROM lenders")
    if cursor.fetchone()[0] == 0:
        lenders_to_seed = [
            # SBI
            ('State Bank of India', 'SBI Express Personal Loan', 'Personal', 720, 25000, 0.50, 11.0, 1.0, 1000, 0.5, 3.0, 1, 7, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (6 months);Form 16'),
            ('State Bank of India', 'SBI Maxgain Home Loan', 'Home', 700, 30000, 0.55, 8.5, 0.5, 5000, 1.0, 0.0, 5, 30, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (6 months);Property Sale Agreement;Property Title Deeds'),
            ('State Bank of India', 'SBI Student Loan', 'Education', 600, 15000, 0.60, 9.5, 0.0, 0.0, 0.0, 0.0, 3, 15, 
             'PAN Card;Aadhaar Card;Admission Letter;Fee Structure document;Co-borrower Income Proof;Co-borrower PAN and Aadhaar'),
            
            # HDFC
            ('HDFC Bank', 'HDFC Personal Loan', 'Personal', 750, 35000, 0.45, 10.5, 1.5, 1500, 0.8, 4.0, 1, 5, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (3 months);Form 16'),
            ('HDFC Bank', 'HDFC Reach Home Loan', 'Home', 720, 40000, 0.50, 8.75, 0.5, 3000, 1.2, 0.0, 5, 30, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (6 months);Property Valuation Report'),
            ('HDFC Bank', 'HDFC Business Growth Loan', 'Business', 700, 50000, 0.40, 15.0, 2.0, 2000, 0.5, 2.0, 1, 5, 
             'PAN Card;Aadhaar Card;ITR (2 years);Business Registration Certificate;GST Registration;Bank Statement (12 months)'),
            
            # ICICI
            ('ICICI Bank', 'ICICI Personal Loan', 'Personal', 730, 30000, 0.50, 10.75, 1.25, 999, 0.6, 3.5, 1, 6, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (3 months)'),
            ('ICICI Bank', 'ICICI Business Instalment Loan', 'Business', 720, 60000, 0.45, 14.5, 1.75, 5000, 0.75, 3.0, 1, 5, 
             'PAN Card;Aadhaar Card;ITR (2 years);GST Returns;Bank Statement (12 months);Business Address Proof'),
            
            # Axis
            ('Axis Bank', 'Axis Prime Education Loan', 'Education', 620, 20000, 0.55, 9.8, 0.5, 1000, 0.5, 0.0, 3, 15, 
             'PAN Card;Aadhaar Card;Admission Letter;Fee Structure document;Co-borrower PAN and Aadhaar;Co-borrower 6-month Bank Statement'),
            
            # Bank of Baroda
            ('Bank of Baroda', 'Baroda Home Loan', 'Home', 680, 25000, 0.60, 8.4, 0.25, 2500, 0.8, 0.0, 5, 30, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (6 months);Property Title Deed;NOC from Builder'),
            ('Bank of Baroda', 'Baroda Personal Loan', 'Personal', 700, 20000, 0.50, 11.5, 1.0, 500, 0.5, 2.0, 1, 5, 
             'PAN Card;Aadhaar Card;Salary Slips (3 months);Bank Statement (6 months)')
        ]
        cursor.executemany('''
            INSERT INTO lenders (
                name, loan_name, loan_type, min_credit_score, min_income, max_dti,
                interest_rate, processing_fee_pct, flat_processing_fee,
                insurance_premium_pct, prepayment_penalty_pct, min_tenure_years, max_tenure_years, required_docs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', lenders_to_seed)
        print("Lenders seeded successfully.")

    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == '__main__':
    init_db()
