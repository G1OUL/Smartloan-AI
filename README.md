# SmartLoan AI – AI-Powered Loan Advisory Platform

![SmartLoan AI](https://img.shields.io/badge/SmartLoan-AI%20Fintech-8b5cf6)
![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Framework-green.svg)
![Scikit-Learn](https://img.shields.io/badge/AI%2FML-Scikit--Learn-orange.svg)
![Multilingual](https://img.shields.io/badge/Languages-EN%20%7C%20HI%20%7C%20MR%20%7C%20GU%20%7C%20TA-cyan.svg)

---

## 1. Introduction & Overview
In today's fast-paced financial world, taking a loan has become essential for education, home ownership, business, or personal needs. Yet for millions, especially first-time borrowers in India, the process remains complex and opaque. Most applicants choose loans based only on interest rates without understanding approval chances, total borrowing cost, or hidden charges.

**SmartLoan AI** is an advanced, web-based platform that combines **Expert Rule-based Underwriting (Phase 1)** with **Scikit-Learn Random Forest Machine Learning (Phase 2)** to provide personalized loan recommendations, approval probability scores, hidden cost transparency, document guidance, and conversational advisory—all through a single application.

---

## 2. Key Features

### ⚡ Approval Probability Score
- Predicts the likelihood of loan approval from different banks based on borrower financial profile (CIBIL, DTI, monthly income, employment status).
- Offers **AI Decision Engine Mode Selector**:
  - **AI Ensemble**: Balanced blend of expert underwriting logic and trained ML models.
  - **Phase 1: Rule Engine**: Deterministic banking policies.
  - **Phase 2: Machine Learning**: Random Forest classifier trained on borrower profiles.

### 🏦 One Application, Multiple Banks
- Fill a single unified questionnaire and immediately compare offers from top Indian lenders (**State Bank of India, HDFC Bank, ICICI Bank, Axis Bank, Bank of Baroda**).
- Eliminates repetitive paperwork and prevents multiple hard inquiries on your credit report.

### 💡 Hidden Cost Transparency & Grand Total Cost
- Calculates and breaks down all upfront and hidden costs:
  - Upfront processing fees (percentage + flat)
  - Mandatory loan insurance premiums
  - Net disbursed amount deposited into bank account
  - Prepayment penalties (highlighting 0% penalty loans for flexible early payoff)
  - Lifetime interest and Grand Total Borrowing Cost

### 📋 Document Assistant & DigiLocker Guidance
- Identifies required documents dynamically based on loan type (Personal, Home, Education, Business) and employment (Salaried, Self-Employed, Student).
- Provides India-specific guidance for retrieving missing documents (e.g. DigiLocker instant eKYC, Income Tax e-filing portal for ITR / Form 16, NetBanking e-statements).
- Built-in **Document Readiness Check** simulator.

### 🌐 Regional Language Support
- Switch between 5 languages in real-time without reloading:
  - **English (EN)**
  - **हिंदी (Hindi - HI)**
  - **मराठी (Marathi - MR)**
  - **ગુજરાતી (Gujarati - GU)**
  - **தமிழ் (Tamil - TA)**

### 📈 Interactive CIBIL Score Simulator
- Visual score planner: simulate the impact of paying down credit card utilization below 30%, clearing overdue accounts, enabling auto-debit (NACH), and avoiding direct multi-bank inquiries.
- Displays projected score increases, new approval odds brackets, and estimated interest rate discounts.

### 📊 Smart EMI Calculator & Optimizer
- Standard interactive sliders for loan amount, tenure, and interest rate with live repayment breakdown.
- **Smart EMI Optimizer**: Enter your comfortable monthly budget, and the tool automatically identifies the optimal tenure to minimize lifetime interest while staying within budget.

### 🤖 AI Financial Coach (Conversational Chatbot)
- Floating assistant available across all pages.
- Answers borrower queries regarding CIBIL improvement, DTI ratios, hidden banking charges, and document requirements in all 5 supported languages.

---

## 3. User Roles

| Role | Access & Capabilities |
| :--- | :--- |
| **Guest User** | Can explore the platform, use the EMI Calculator & Optimizer, read educational literacy guides, and test the CIBIL Simulator. |
| **Registered Borrower** | Has a profile, saves search queries to history, tracks saved loan offers, and accesses personalized document guidance. |
| **First-Time Applicant** | Receives simplified jargon-free explanations, guided warning tooltips, and beginner borrowing tips. |
| **Administrator** | Accesses the Admin Portal: lender product management (Add, Edit, Delete loan products), user role management, and analytics dashboard. |

---

## 4. Technology Stack
- **Frontend**: HTML5, Vanilla CSS3 (Custom Fintech Glassmorphism Design System), JavaScript (ES6+ SPA architecture, client-side i18n localization).
- **Backend**: Python 3.9+, Flask Framework, Werkzeug security hashing.
- **Database**: SQLite (`database.db`) with automatic schema initialization and seeding.
- **AI / Machine Learning**: Scikit-Learn (Random Forest Classifier Pipeline with OneHotEncoding and ColumnTransformer), Pandas, NumPy, Joblib.

---

## 5. Getting Started & Running Locally

### Prerequisites
- Python 3.9 or higher installed.

### Installation
1. Clone the repository or navigate to the project directory:
   ```bash
   cd c:\Users\HP\OneDrive\Desktop\Smartai
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your web browser and visit:
   ```
   http://127.0.0.1:5000
   ```

> **Note**: On first launch, `app.py` will automatically initialize `database.db` with default users and lenders, and warm up / train the machine learning pipeline (`loan_classifier.pkl`).

---

## 6. Demo Login Credentials

| Username | Password | Role | Features |
| :--- | :--- | :--- | :--- |
| `borrower` | `borrower123` | Registered Borrower | Saves searches, loan history, document assistant |
| `newbie` | `newbie123` | First-Time Applicant | Special guided tooltips and beginner advisory |
| `admin` | `admin123` | Administrator | Admin portal, lender CRUD, user management, analytics |

*(You can also register a new account anytime from the **Login / Sign Up** tab!)*

---

## 7. Verification Tests

Run the full automated test suite anytime:
```bash
python verify_full_suite.py
```
This script validates:
- Database creation & table seeding
- ML pipeline training & inference
- Financial EMI calculation math
- Rule Engine vs ML Engine vs Ensemble scoring
- Underwriting policy checks (Low CIBIL, High DTI)
- REST APIs (`/api/loans/search`, `/api/cibil/optimize`, `/api/emi/optimize`, `/api/coach/chat` in all 5 languages).

---

## 8. License & Declaration
Submitted as part of the project curriculum for **SmartLoan AI – AI-Powered Loan Advisory Platform**.
