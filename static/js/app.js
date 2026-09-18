let currentUser = null;
let currentLang = 'en';
let cachedOffers = [];
let selectedCompareIds = [];

document.addEventListener("DOMContentLoaded", () => {
    // 1. Check Auth Status on load
    checkAuth();
    
    // 2. Setup Language Preference
    const savedLang = localStorage.getItem("smartloan_lang");
    if (savedLang && translations[savedLang]) {
        currentLang = savedLang;
    }
    const langSelect = document.getElementById("lang-select");
    if (langSelect) langSelect.value = currentLang;
    applyTranslations();

    // 3. Setup Navigation Event Listeners
    setupNav();

    // 4. Setup Form Event Listeners
    setupForms();

    // 5. Setup Live Calculator Sliders
    setupCalculatorSliders();

    // 6. Setup CIBIL Simulator
    setupCibilSimulator();
});

// Auth Status Checker
function checkAuth() {
    fetch('/api/auth/me')
        .then(res => res.json())
        .then(data => {
            if (data.user) {
                currentUser = data.user;
                updateUserUI();
                loadHistory();
            } else {
                currentUser = null;
                updateUserUI();
            }
            applyTranslations();
        })
        .catch(err => console.error("Auth check failed:", err));
}

// UI updates based on logged in user
function updateUserUI() {
    const guestAlert = document.getElementById("guest-alert");
    const navLogin = document.getElementById("nav-login-item");
    const navLogout = document.getElementById("nav-logout-item");
    const navHistory = document.getElementById("nav-history-item");
    const navAdmin = document.getElementById("nav-admin-item");
    
    const userWidget = document.getElementById("sidebar-user-widget");
    const userAvatar = document.getElementById("widget-avatar");
    const usernameLbl = document.getElementById("widget-username");
    const userTypeLbl = document.getElementById("widget-usertype");

    if (currentUser) {
        if (guestAlert) guestAlert.style.display = 'none';
        if (navLogin) navLogin.style.display = 'none';
        if (navLogout) navLogout.style.display = 'block';
        if (navHistory) navHistory.style.display = 'block';
        
        if (currentUser.user_type === 'admin') {
            if (navAdmin) navAdmin.style.display = 'block';
            loadAdminLenders();
            loadAdminAnalytics();
            loadAdminUsers();
        } else {
            if (navAdmin) navAdmin.style.display = 'none';
        }

        if (userWidget) {
            userWidget.style.display = 'flex';
            if (userAvatar) userAvatar.innerText = currentUser.username.substring(0, 2).toUpperCase();
            if (usernameLbl) usernameLbl.innerText = currentUser.username;
            if (userTypeLbl) userTypeLbl.innerText = currentUser.user_type === 'first_time' ? 'First-Time Applicant' : currentUser.user_type;
        }

        const tipWidget = document.getElementById("first-time-tip-widget");
        if (currentUser.user_type === 'first_time') {
            if (tipWidget) tipWidget.style.display = 'flex';
        } else {
            if (tipWidget) tipWidget.style.display = 'none';
        }
    } else {
        if (guestAlert) guestAlert.style.display = 'flex';
        if (navLogin) navLogin.style.display = 'block';
        if (navLogout) navLogout.style.display = 'none';
        if (navHistory) navHistory.style.display = 'none';
        if (navAdmin) navAdmin.style.display = 'none';
        if (userWidget) userWidget.style.display = 'none';
        
        const tipWidget = document.getElementById("first-time-tip-widget");
        if (tipWidget) tipWidget.style.display = 'none';
    }
}

// Navigation handling (SPA Tabs)
function setupNav() {
    const links = document.querySelectorAll(".menu-item a");
    links.forEach(link => {
        link.addEventListener("click", (e) => {
            const parent = link.parentElement;
            if (parent.id === "nav-logout-item") {
                e.preventDefault();
                logoutUser();
                return;
            }
            
            e.preventDefault();
            const targetTabId = link.getAttribute("href").substring(1);
            switchTab(targetTabId);
        });
    });
}

function switchTab(tabId) {
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach(item => item.classList.remove("active"));
    
    const activeLink = document.querySelector(`.menu-item a[href="#${tabId}"]`);
    if (activeLink) {
        activeLink.parentElement.classList.add("active");
    }

    const tabs = document.querySelectorAll(".tab-container");
    tabs.forEach(tab => {
        tab.classList.remove("active");
        if (tab.id === tabId) {
            tab.classList.add("active");
        }
    });

    if (tabId === 'history' && currentUser) {
        loadHistory();
    }
    if (tabId === 'cibil-sim') {
        calculateCibilSimulation();
    }
}

// Handle client-side language switching
function changeLanguage(lang) {
    currentLang = lang;
    localStorage.setItem("smartloan_lang", lang);
    applyTranslations();
    
    if (cachedOffers.length > 0) {
        renderOffers(cachedOffers);
    }
    calculateCibilSimulation();
}

// Look through elements and update texts
function applyTranslations() {
    const dict = translations[currentLang] || translations['en'];
    
    const elements = document.querySelectorAll("[data-i18n]");
    elements.forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (dict[key]) {
            el.innerText = dict[key];
        }
    });

    const placeholders = document.querySelectorAll("[data-i18n-placeholder]");
    placeholders.forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (dict[key]) {
            el.setAttribute("placeholder", dict[key]);
        }
    });
}

// Form submissions and handlers
function setupForms() {
    // 1. Eligibility Form Submission
    const eligibilityForm = document.getElementById("eligibility-form");
    if (eligibilityForm) {
        eligibilityForm.addEventListener("submit", (e) => {
            e.preventDefault();
            
            const income = parseFloat(document.getElementById("form-income").value);
            const emis = parseFloat(document.getElementById("form-emis").value) || 0;
            const creditScore = parseInt(document.getElementById("form-credit").value);
            const amount = parseFloat(document.getElementById("form-amount").value);
            const tenure = parseInt(document.getElementById("form-tenure").value);
            const loanType = document.getElementById("form-loan-type").value;
            const employment = document.getElementById("form-employment").value;
            const engineMode = document.getElementById("form-engine-mode") ? document.getElementById("form-engine-mode").value : 'ensemble';
            
            if (!income || !creditScore || !amount || !tenure) {
                alert("Please fill all required fields with non-zero values.");
                return;
            }

            const requestData = {
                income: income,
                existing_emis: emis,
                credit_score: creditScore,
                loan_amount: amount,
                tenure_years: tenure,
                loan_type: loanType,
                employment_type: employment,
                engine_mode: engineMode
            };

            fetch('/api/loans/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    cachedOffers = data.offers;
                    selectedCompareIds = [];
                    updateCompareTray();
                    
                    // Update active engine badge
                    const badgeLabel = document.getElementById("engine-badge-label");
                    if (badgeLabel) {
                        badgeLabel.innerText = engineMode === 'rule' ? 'Phase 1: Rule Engine' : 
                                               engineMode === 'ml' ? 'Phase 2: ML Random Forest' : 'AI Ensemble (Rule + ML)';
                    }

                    // Render recommendation dashboard
                    renderOffers(data.offers);

                    // Render document checklist based on type
                    setupDocumentChecklist(loanType, employment);

                    // Update quick CIBIL card in Tab 2
                    updateQuickCibilCard(creditScore);

                    // Smooth scroll to results
                    document.getElementById("results-section").scrollIntoView({ behavior: 'smooth' });
                }
            })
            .catch(err => {
                console.error("Search failed:", err);
                alert("Could not process application. Please try again.");
            });
        });
    }

    // 2. Login Form Submission
    const loginForm = document.getElementById("login-form-el");
    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const username = document.getElementById("login-username").value;
            const password = document.getElementById("login-password").value;
            
            fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    currentUser = data.user;
                    updateUserUI();
                    switchTab('dashboard');
                }
            })
            .catch(err => console.error("Login failed:", err));
        });
    }

    // 3. Registration Form Submission
    const registerForm = document.getElementById("register-form-el");
    if (registerForm) {
        registerForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const username = document.getElementById("reg-username").value;
            const email = document.getElementById("reg-email").value;
            const password = document.getElementById("reg-password").value;
            const isFirstTime = document.getElementById("reg-first-time").value;
            
            fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    email,
                    password,
                    user_type: isFirstTime
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    alert(data.message);
                    toggleAuthTab('login');
                }
            })
            .catch(err => console.error("Registration failed:", err));
        });
    }

    // 4. Admin Add Lender Form Submission
    const adminForm = document.getElementById("admin-add-lender-form");
    if (adminForm) {
        adminForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const payload = {
                name: document.getElementById("adm-name").value,
                loan_name: document.getElementById("adm-loan-name").value,
                loan_type: document.getElementById("adm-loan-type").value,
                min_credit_score: parseInt(document.getElementById("adm-min-credit").value),
                min_income: parseFloat(document.getElementById("adm-min-income").value),
                max_dti: parseFloat(document.getElementById("adm-max-dti").value),
                interest_rate: parseFloat(document.getElementById("adm-rate").value),
                processing_fee_pct: parseFloat(document.getElementById("adm-fee-pct").value),
                flat_processing_fee: parseFloat(document.getElementById("adm-fee-flat").value),
                insurance_premium_pct: parseFloat(document.getElementById("adm-ins-pct").value),
                prepayment_penalty_pct: parseFloat(document.getElementById("adm-prep-pct").value),
                min_tenure_years: parseInt(document.getElementById("adm-tenure-min").value),
                max_tenure_years: parseInt(document.getElementById("adm-tenure-max").value),
                required_docs: document.getElementById("adm-docs").value
            };

            fetch('/api/admin/lenders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    alert(data.message);
                    adminForm.reset();
                    loadAdminLenders();
                    loadAdminAnalytics();
                }
            })
            .catch(err => console.error("Failed to add lender:", err));
        });
    }
}

// Log out user
function logoutUser() {
    fetch('/api/auth/logout', { method: 'POST' })
        .then(res => res.json())
        .then(() => {
            currentUser = null;
            updateUserUI();
            switchTab('dashboard');
        });
}

// Auth Tabs Toggle
function toggleAuthTab(mode) {
    const loginTab = document.getElementById("auth-tab-login-btn");
    const regTab = document.getElementById("auth-tab-reg-btn");
    const loginBox = document.getElementById("login-form-box");
    const regBox = document.getElementById("register-form-box");

    if (mode === 'login') {
        loginTab.classList.add("active");
        regTab.classList.remove("active");
        loginBox.style.display = 'block';
        regBox.style.display = 'none';
    } else {
        loginTab.classList.remove("active");
        regTab.classList.add("active");
        loginBox.style.display = 'none';
        regBox.style.display = 'block';
    }
}

// Calculator Sliders Logic
function setupCalculatorSliders() {
    const sliders = ['calc-principal-range', 'calc-rate-range', 'calc-tenure-range'];
    sliders.forEach(id => {
        const slider = document.getElementById(id);
        if (slider) {
            slider.addEventListener("input", runCalculator);
        }
    });
    runCalculator();
}

function runCalculator() {
    const p = parseFloat(document.getElementById("calc-principal-range").value);
    const rVal = parseFloat(document.getElementById("calc-rate-range").value);
    const nYears = parseInt(document.getElementById("calc-tenure-range").value);

    document.getElementById("calc-principal-val").innerText = "₹" + p.toLocaleString('en-IN');
    document.getElementById("calc-rate-val").innerText = rVal + "%";
    document.getElementById("calc-tenure-val").innerText = nYears + " Years";

    const optContext = document.getElementById("opt-context");
    if (optContext) {
        optContext.value = `₹${p.toLocaleString('en-IN')} @ ${rVal}% p.a.`;
    }

    const r = (rVal / 12) / 100;
    const n = nYears * 12;
    let emi = 0;
    if (r === 0) {
        emi = p / n;
    } else {
        emi = p * r * (Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
    }

    const totalPayable = emi * n;
    const totalInterest = totalPayable - p;

    document.getElementById("calc-emi-result").innerText = "₹" + Math.round(emi).toLocaleString('en-IN');
    document.getElementById("calc-principal-result").innerText = "₹" + p.toLocaleString('en-IN');
    document.getElementById("calc-interest-result").innerText = "₹" + Math.round(totalInterest).toLocaleString('en-IN');
    document.getElementById("calc-total-result").innerText = "₹" + Math.round(totalPayable).toLocaleString('en-IN');
}

// Smart EMI Optimizer
window.runEmiOptimization = function() {
    const p = parseFloat(document.getElementById("calc-principal-range").value);
    const rVal = parseFloat(document.getElementById("calc-rate-range").value);
    const targetBudget = parseFloat(document.getElementById("opt-budget").value) || 12000;

    fetch('/api/emi/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            loan_amount: p,
            interest_rate: rVal,
            target_budget: targetBudget
        })
    })
    .then(res => res.json())
    .then(data => {
        const resultsBox = document.getElementById("emi-opt-results");
        resultsBox.style.display = 'block';

        document.getElementById("opt-rec-tenure").innerText = `${data.recommended_tenure_years} Years`;
        document.getElementById("opt-rec-emi").innerText = `₹${Math.round(data.recommended_monthly_emi).toLocaleString('en-IN')}`;
        document.getElementById("opt-rec-savings").innerText = `₹${Math.round(data.interest_saved_vs_longer_tenure).toLocaleString('en-IN')}`;
        
        document.getElementById("opt-rec-advice").innerText = 
            `💡 By paying ₹${Math.round(data.recommended_monthly_emi).toLocaleString('en-IN')} over ${data.recommended_tenure_years} years, you remain within your ₹${targetBudget.toLocaleString('en-IN')} monthly budget while saving ₹${Math.round(data.interest_saved_vs_longer_tenure).toLocaleString('en-IN')} in total interest!`;
    })
    .catch(err => console.error("EMI optimization failed:", err));
};

// Render Recommendation Offers
function renderOffers(offers) {
    const tableBody = document.getElementById("offers-table-body");
    tableBody.innerHTML = "";

    if (offers.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">No loan products found for this type. Please contact support.</td></tr>`;
        return;
    }

    offers.forEach(offer => {
        const tr = document.createElement("tr");
        if (!offer.is_eligible) {
            tr.style.opacity = "0.55";
        }

        let circleClass = 'green';
        if (offer.approval_probability < 50) circleClass = 'red';
        else if (offer.approval_probability < 80) circleClass = 'yellow';
        
        const strokeOffset = 113.1 - (offer.approval_probability / 100) * 113.1;
        
        let actionCol = '';
        if (offer.is_eligible) {
            actionCol = `
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <button class="btn btn-secondary btn-sm" onclick="showLoanDetails(${offer.lender_id})">
                        ${translations[currentLang].btn_view_details}
                    </button>
                    <input type="checkbox" class="custom-checkbox" id="comp-check-${offer.lender_id}" onchange="toggleCompare(${offer.lender_id})">
                </div>
            `;
        } else {
            actionCol = `
                <span class="badge badge-danger">${translations[currentLang].msg_not_eligible}</span>
                <button class="btn btn-outline btn-sm" style="margin-left: 0.5rem;" onclick="showLoanDetails(${offer.lender_id})">?</button>
            `;
        }

        // Dual Engine Score breakdown row
        const dualScoreHTML = (offer.rule_probability !== undefined && offer.ml_probability !== undefined) ? `
            <div class="dual-engine-row">
                <span class="engine-tag" title="Phase 1 Rule Probability">Rule: ${offer.rule_probability}%</span>
                <span class="engine-tag" title="Phase 2 ML Random Forest Probability">ML: ${offer.ml_probability}%</span>
            </div>
        ` : '';

        // Factor badges
        const prepayBadge = offer.prepayment_penalty_pct === 0 ? 
            `<span class="factor-badge" style="background: rgba(16,185,129,0.1); color:#34d399; border-color: rgba(16,185,129,0.25);">0% Prepayment Penalty</span>` :
            `<span class="factor-badge">${offer.prepayment_penalty_pct}% Prepayment</span>`;

        const feeBadge = offer.processing_fee === 0 ?
            `<span class="factor-badge" style="background: rgba(16,185,129,0.1); color:#34d399; border-color: rgba(16,185,129,0.25);">Zero Processing Fee</span>` :
            `<span class="factor-badge">Fee: ₹${Math.round(offer.processing_fee).toLocaleString('en-IN')}</span>`;

        tr.innerHTML = `
            <td>
                <div style="font-weight: 700; color: #fff; font-size: 1rem;">${offer.lender_name}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.35rem;">${offer.loan_name}</div>
                <div class="factor-tags-grid">
                    ${prepayBadge}
                    ${feeBadge}
                </div>
            </td>
            <td style="font-family: var(--font-heading); font-weight: 600; color: var(--secondary); font-size: 1.05rem;">${offer.interest_rate}%</td>
            <td style="font-weight: 700; font-size: 1rem;">₹${Math.round(offer.monthly_emi).toLocaleString('en-IN')}</td>
            <td>
                <div class="prob-container">
                    <div class="circle-progress">
                        <svg width="44" height="44">
                            <circle class="circle-bg" cx="22" cy="22" r="18" />
                            <circle class="circle-fill ${circleClass}" cx="22" cy="22" r="18" 
                                    stroke-dasharray="113.1" stroke-dashoffset="${strokeOffset}" />
                        </svg>
                        <div class="prob-val-lbl">${offer.approval_probability}%</div>
                    </div>
                    ${dualScoreHTML}
                </div>
            </td>
            <td>
                <div style="font-family: var(--font-heading); font-weight: 700; font-size: 1rem;">₹${Math.round(offer.total_cost).toLocaleString('en-IN')}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">Net: ₹${Math.round(offer.net_disbursement).toLocaleString('en-IN')}</div>
            </td>
            <td>${actionCol}</td>
        `;
        tableBody.appendChild(tr);
    });
}

// Show Loan Details Modal
window.showLoanDetails = function(lenderId) {
    const offer = cachedOffers.find(o => o.lender_id === lenderId);
    if (!offer) return;
    const modal = document.getElementById("details-modal");
    
    document.getElementById("modal-lender-title").innerText = offer.lender_name;
    document.getElementById("modal-product-title").innerText = offer.loan_name;
    
    document.getElementById("det-emi-val").innerText = "₹" + Math.round(offer.monthly_emi).toLocaleString('en-IN');
    document.getElementById("det-interest-val").innerText = "₹" + Math.round(offer.total_interest).toLocaleString('en-IN');
    document.getElementById("det-fee-val").innerText = "₹" + Math.round(offer.processing_fee).toLocaleString('en-IN');
    document.getElementById("det-insurance-val").innerText = "₹" + Math.round(offer.insurance_cost).toLocaleString('en-IN');
    
    const netVal = document.getElementById("det-net-val");
    if (netVal) {
        netVal.innerText = "₹" + Math.round(offer.net_disbursement).toLocaleString('en-IN');
    }

    document.getElementById("det-total-val").innerText = "₹" + Math.round(offer.total_cost).toLocaleString('en-IN');
    document.getElementById("det-prepayment-val").innerText = offer.prepayment_penalty_pct > 0 ? `${offer.prepayment_penalty_pct}% penalty` : "0% (Nil - Full Early Repayment Freedom)";
    
    document.getElementById("det-advice-val").innerText = offer.advice_commentary;

    const docsContainer = document.getElementById("det-docs-list");
    docsContainer.innerHTML = "";
    offer.required_docs.forEach(doc => {
        const li = document.createElement("li");
        li.style.fontSize = "0.9rem";
        li.style.color = "var(--text-secondary)";
        li.style.marginBottom = "0.25rem";
        li.innerText = "📄 " + doc;
        docsContainer.appendChild(li);
    });

    const reasonContainer = document.getElementById("det-rejection-reasons");
    if (offer.rejection_reasons && offer.rejection_reasons.length > 0) {
        reasonContainer.style.display = "block";
        const list = document.getElementById("det-rejection-list");
        list.innerHTML = "";
        offer.rejection_reasons.forEach(r => {
            const li = document.createElement("li");
            li.style.fontSize = "0.85rem";
            li.style.color = "var(--accent-red)";
            li.innerText = "⚠️ " + r;
            list.appendChild(li);
        });
    } else {
        reasonContainer.style.display = "none";
    }

    modal.classList.add("active");
    applyTranslations();
};

window.closeModal = function() {
    document.getElementById("details-modal").classList.remove("active");
    document.getElementById("compare-modal").classList.remove("active");
};

// Side-by-Side Comparison Logic
window.toggleCompare = function(lenderId) {
    const idx = selectedCompareIds.indexOf(lenderId);
    const cb = document.getElementById(`comp-check-${lenderId}`);
    if (cb.checked) {
        if (selectedCompareIds.length >= 3) {
            cb.checked = false;
            alert("You can select up to 3 loans to compare.");
            return;
        }
        if (idx === -1) {
            selectedCompareIds.push(lenderId);
        }
    } else {
        if (idx !== -1) {
            selectedCompareIds.splice(idx, 1);
        }
    }
    updateCompareTray();
};

function updateCompareTray() {
    const tray = document.getElementById("compare-tray");
    const container = document.getElementById("compare-bubbles");
    if (selectedCompareIds.length > 0) {
        container.innerHTML = "";
        selectedCompareIds.forEach(id => {
            const offer = cachedOffers.find(o => o.lender_id === id);
            if (offer) {
                const bubble = document.createElement("div");
                bubble.className = "compare-bubble";
                bubble.innerHTML = `
                    <span>${offer.lender_name}</span>
                    <button class="compare-bubble-remove" onclick="removeCompareBubble(${id})">×</button>
                `;
                container.appendChild(bubble);
            }
        });
        tray.classList.add("active");
    } else {
        tray.classList.remove("active");
    }

    const compBtn = document.getElementById("compare-action-btn");
    if (selectedCompareIds.length >= 2) {
        compBtn.disabled = false;
        compBtn.style.opacity = "1";
    } else {
        compBtn.disabled = true;
        compBtn.style.opacity = "0.5";
    }
}

window.removeCompareBubble = function(lenderId) {
    const cb = document.getElementById(`comp-check-${lenderId}`);
    if (cb) cb.checked = false;
    
    const idx = selectedCompareIds.indexOf(lenderId);
    if (idx !== -1) {
        selectedCompareIds.splice(idx, 1);
    }
    updateCompareTray();
};

window.triggerCompareResults = function() {
    if (selectedCompareIds.length < 2) return;
    const modal = document.getElementById("compare-modal");
    const grid = document.getElementById("compare-grid-container");
    grid.innerHTML = "";

    const selectOffers = cachedOffers.filter(o => selectedCompareIds.includes(o.lender_id));
    
    let winnerId = -1;
    let minCost = Infinity;
    selectOffers.forEach(o => {
        if (o.is_eligible && o.total_cost < minCost) {
            minCost = o.total_cost;
            winnerId = o.lender_id;
        }
    });

    selectOffers.forEach(offer => {
        const isWinner = offer.lender_id === winnerId;
        const card = document.createElement("div");
        card.className = `compare-card ${isWinner ? 'winner' : ''}`;
        
        card.innerHTML = `
            <div class="compare-card-title">
                <h4>${offer.lender_name}</h4>
                <p style="font-size: 0.75rem; color: var(--secondary);">${offer.loan_name}</p>
                ${isWinner ? '<span class="badge badge-success" style="margin-top:0.35rem;">Lowest Lifetime Cost</span>' : ''}
            </div>
            <div class="compare-metric prob-highlight">
                <span>Approval Probability</span>
                <span style="color: ${offer.approval_probability >= 80 ? 'var(--accent-green)' : offer.approval_probability >= 50 ? 'var(--accent-yellow)' : 'var(--accent-red)'}">
                    ${offer.approval_probability}%
                </span>
            </div>
            <div class="compare-metric">
                <span>Interest Rate (p.a.)</span>
                <span style="font-weight: 700; color: #fff;">${offer.interest_rate}%</span>
            </div>
            <div class="compare-metric">
                <span>Estimated Monthly EMI</span>
                <span>₹${Math.round(offer.monthly_emi).toLocaleString('en-IN')}</span>
            </div>
            <div class="compare-metric">
                <span>Total Interest Paid</span>
                <span>₹${Math.round(offer.total_interest).toLocaleString('en-IN')}</span>
            </div>
            <div class="compare-metric">
                <span>Processing Fees</span>
                <span>₹${Math.round(offer.processing_fee).toLocaleString('en-IN')}</span>
            </div>
            <div class="compare-metric">
                <span>Insurance Premium</span>
                <span>₹${Math.round(offer.insurance_cost).toLocaleString('en-IN')}</span>
            </div>
            <div class="compare-metric">
                <span>Prepayment Penalty</span>
                <span>${offer.prepayment_penalty_pct}%</span>
            </div>
            <div class="compare-metric" style="border-bottom: none; font-weight: 800; font-size: 1.15rem; color: #fff; margin-top: 1rem;">
                <span>Total Borrowing Cost</span>
                <span style="color: var(--accent-green);">₹${Math.round(offer.total_cost).toLocaleString('en-IN')}</span>
            </div>
        `;
        grid.appendChild(card);
    });
    modal.classList.add("active");
};

// Document Assistant Checkbox / Guidance Logic
function setupDocumentChecklist(loanType, employment) {
    const listContainer = document.getElementById("document-checklist-items");
    listContainer.innerHTML = "";
    
    const guidances = {
        'PAN Card': 'doc_guide_pan',
        'Aadhaar Card': 'doc_guide_aadhaar',
        'Salary Slips (3 months)': 'doc_guide_salary',
        'Salary Slips': 'doc_guide_salary',
        'Bank Statement (6 months)': 'doc_guide_statement',
        'Bank Statement (3 months)': 'doc_guide_statement',
        'Bank Statement (12 months)': 'doc_guide_statement',
        'Form 16': 'doc_guide_salary',
        'ITR (2 years)': 'doc_guide_itr',
        'Admission Letter': 'doc_guide_admission',
        'Fee Structure document': 'doc_guide_admission',
        'Property Sale Agreement': 'doc_guide_property',
        'Property Title Deeds': 'doc_guide_property',
        'Co-borrower Income Proof': 'doc_guide_salary'
    };

    let reqDocs = ['PAN Card', 'Aadhaar Card'];
    if (loanType === 'Personal' || loanType === 'Home') {
        if (employment === 'Salaried') {
            reqDocs.push('Salary Slips (3 months)', 'Bank Statement (6 months)', 'Form 16');
        } else if (employment === 'Self-Employed') {
            reqDocs.push('ITR (2 years)', 'Bank Statement (12 months)');
        }
    }
    if (loanType === 'Home') {
        reqDocs.push('Property Sale Agreement', 'Property Title Deeds');
    }
    if (loanType === 'Education') {
        reqDocs.push('Admission Letter', 'Fee Structure document', 'Co-borrower Income Proof');
    }
    if (loanType === 'Business') {
        reqDocs.push('ITR (2 years)', 'Bank Statement (12 months)');
    }

    reqDocs = [...new Set(reqDocs)];
    reqDocs.forEach((doc, idx) => {
        const item = document.createElement("div");
        item.className = "doc-check-item";
        item.id = `doc-item-${idx}`;
        item.onclick = () => toggleDocChecked(idx);
        item.innerHTML = `
            <input type="checkbox" class="custom-checkbox" id="doc-cb-${idx}">
            <span style="font-weight: 500;">${doc}</span>
            <span style="margin-left: auto; font-size: 0.72rem; color: #38bdf8; background: rgba(6,182,212,0.1); padding: 0.1rem 0.4rem; border-radius: 4px;">DigiLocker</span>
        `;
        listContainer.appendChild(item);
    });

    const guideContainer = document.getElementById("document-checklist-guidance");
    guideContainer.innerHTML = "";
    reqDocs.forEach(doc => {
        const key = guidances[doc];
        if (key && translations['en'][key]) {
            const li = document.createElement("div");
            li.style.marginBottom = "0.75rem";
            li.style.fontSize = "0.9rem";
            li.innerHTML = `<strong>${doc}:</strong> <span data-i18n="${key}">${translations[currentLang][key]}</span>`;
            guideContainer.appendChild(li);
        }
    });

    document.getElementById("document-assistant-card").style.display = "block";
}

function toggleDocChecked(idx) {
    const cb = document.getElementById(`doc-cb-${idx}`);
    const item = document.getElementById(`doc-item-${idx}`);
    
    cb.checked = !cb.checked;
    if (cb.checked) {
        item.classList.add("checked");
    } else {
        item.classList.remove("checked");
    }
}

// Document Readiness Check
window.runDocumentReadinessCheck = function() {
    const total = document.querySelectorAll(".doc-check-item").length;
    const checked = document.querySelectorAll(".doc-check-item.checked").length;
    const banner = document.getElementById("doc-readiness-banner");
    banner.style.display = 'block';

    if (total === 0) return;

    if (checked === total) {
        banner.className = 'readiness-banner readiness-success';
        banner.innerText = '✔ 100% Document Readiness. DigiLocker verified documents expedite bank approval by 48 hours!';
    } else {
        banner.className = 'readiness-banner readiness-warning';
        banner.innerText = `⚠️ You have ${checked} of ${total} documents verified. Ensure missing items are obtained via DigiLocker or NetBanking to prevent bank rejection.`;
    }
};

// CIBIL Simulator Setup & Calculations
function setupCibilSimulator() {
    const simInput = document.getElementById("sim-cibil-input");
    if (simInput) {
        simInput.addEventListener("input", calculateCibilSimulation);
    }
    calculateCibilSimulation();
}

window.calculateCibilSimulation = function() {
    const simInput = document.getElementById("sim-cibil-input");
    if (!simInput) return;
    const curScore = parseInt(simInput.value) || 670;

    const actions = [];
    if (document.getElementById("chk-util")?.checked) actions.push('reduce_utilization');
    if (document.getElementById("chk-overdue")?.checked) actions.push('clear_overdue');
    if (document.getElementById("chk-autodebit")?.checked) actions.push('auto_debit');
    if (document.getElementById("chk-inquiries")?.checked) actions.push('avoid_inquiries');
    if (document.getElementById("chk-mix")?.checked) actions.push('credit_mix');

    fetch('/api/cibil/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_score: curScore, actions: actions })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("sim-score-before").innerText = data.current_score;
        document.getElementById("sim-score-after").innerText = data.projected_score;
        document.getElementById("sim-points-badge").innerText = `+${data.points_gain} Points Potential`;
        document.getElementById("sim-odds-before").innerText = `${data.current_approval_odds}%`;
        document.getElementById("sim-odds-after").innerText = `${data.projected_approval_odds}%`;
        document.getElementById("sim-rate-benefit").innerText = data.estimated_rate_discount;
    })
    .catch(err => console.error("CIBIL simulation error:", err));
};

window.applySimulatedScoreToForm = function() {
    const projScore = parseInt(document.getElementById("sim-score-after").innerText) || 750;
    const creditInput = document.getElementById("form-credit");
    if (creditInput) {
        creditInput.value = projScore;
    }
    switchTab('apply');
    alert(`Projected CIBIL Score of ${projScore} applied to Eligibility Application!`);
};

function updateQuickCibilCard(score) {
    const card = document.getElementById("quick-cibil-card");
    if (!card) return;
    card.style.display = 'block';

    const currentElem = document.getElementById("quick-cibil-current");
    const projElem = document.getElementById("quick-cibil-proj");
    const barElem = document.getElementById("quick-cibil-bar");
    
    currentElem.innerText = score;
    const projected = Math.min(900, score + 65);
    projElem.innerText = projected;

    const pct = Math.round(((projected - 300) / 600) * 100);
    barElem.style.width = `${pct}%`;
}

// AI Financial Coach Interactive Chat
window.toggleCoachWindow = function() {
    const win = document.getElementById("coach-window");
    if (win.style.display === 'none' || win.style.display === '') {
        win.style.display = 'flex';
        document.getElementById("coach-input-text").focus();
    } else {
        win.style.display = 'none';
    }
};

window.sendQuickCoachMessage = function(topic) {
    const input = document.getElementById("coach-input-text");
    const prompts = {
        'cibil': 'How can I increase my CIBIL score quickly?',
        'dti': 'What is Debt-to-Income (DTI) ratio and how do banks calculate it?',
        'fees': 'What are the hidden fees and charges in a loan?',
        'docs': 'What documents do I need for a Home Loan?'
    };
    input.value = prompts[topic] || topic;
    handleCoachSubmit(new Event('submit'));
};

window.handleCoachSubmit = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    const input = document.getElementById("coach-input-text");
    const msg = input.value.trim();
    if (!msg) return;

    const msgArea = document.getElementById("coach-messages-area");

    // Append user message
    const userBubble = document.createElement("div");
    userBubble.className = "coach-bubble coach-bubble-user";
    userBubble.innerText = msg;
    msgArea.appendChild(userBubble);

    input.value = "";
    msgArea.scrollTop = msgArea.scrollHeight;

    // Typing indicator
    const typingBubble = document.createElement("div");
    typingBubble.className = "coach-bubble coach-bubble-bot";
    typingBubble.id = "coach-typing";
    typingBubble.innerHTML = `<em>Advisor is thinking...</em>`;
    msgArea.appendChild(typingBubble);
    msgArea.scrollTop = msgArea.scrollHeight;

    fetch('/api/coach/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, language: currentLang })
    })
    .then(res => res.json())
    .then(data => {
        const tBubble = document.getElementById("coach-typing");
        if (tBubble) tBubble.remove();

        const botBubble = document.createElement("div");
        botBubble.className = "coach-bubble coach-bubble-bot";
        botBubble.innerHTML = data.reply;
        msgArea.appendChild(botBubble);
        msgArea.scrollTop = msgArea.scrollHeight;
    })
    .catch(err => {
        const tBubble = document.getElementById("coach-typing");
        if (tBubble) tBubble.remove();
        console.error("Coach chat failed:", err);
    });
};

// Loan History Loader
function loadHistory() {
    fetch('/api/applications/history')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById("history-list-container");
            container.innerHTML = "";
            if (!data.history || data.history.length === 0) {
                container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;" data-i18n="hist_empty">${translations[currentLang].hist_empty}</div>`;
                return;
            }
            data.history.forEach(item => {
                const card = document.createElement("div");
                card.className = "glass-card";
                card.style.marginBottom = "1rem";
                
                const date = new Date(item.created_at).toLocaleDateString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
                });

                let offersHTML = '';
                if (item.saved_offers && item.saved_offers.length > 0) {
                    offersHTML = `
                        <div class="history-saved-cards">
                            ${item.saved_offers.map(o => `
                                <div class="history-saved-mini">
                                    <strong>${o.lender_name}</strong>
                                    <div style="color: var(--secondary); font-size:0.75rem;">ROI: ${o.interest_rate}% | EMI: ₹${Math.round(o.monthly_emi).toLocaleString('en-IN')}</div>
                                    <div style="font-weight: 700; margin-top:0.25rem;">Cost: ₹${Math.round(o.total_cost).toLocaleString('en-IN')}</div>
                                    <div style="color: var(--accent-green); font-size:0.75rem; font-weight:700;">Chance: ${o.approval_probability}%</div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                } else {
                    offersHTML = `<div style="font-size:0.8rem; color:var(--text-muted); margin-top: 0.5rem;">No eligible recommendations found for this query.</div>`;
                }

                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <span class="badge badge-success" style="font-size:0.65rem;">${item.loan_type}</span>
                            <h3 style="margin-top:0.5rem; font-size:1.25rem;">₹${item.loan_amount.toLocaleString('en-IN')} for ${item.tenure_years} Years</h3>
                            <p style="font-size:0.8rem; color:var(--text-muted);">Searched on: ${date} | Income: ₹${item.income.toLocaleString('en-IN')} | CIBIL: ${item.credit_score}</p>
                        </div>
                    </div>
                    ${offersHTML}
                `;
                container.appendChild(card);
            });
        })
        .catch(err => console.error("History fetch failed:", err));
}

// Admin Lender Management
function loadAdminLenders() {
    fetch('/api/admin/lenders')
        .then(res => res.json())
        .then(data => {
            const tableBody = document.getElementById("admin-lenders-table-body");
            tableBody.innerHTML = "";
            if (!data.lenders || data.lenders.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem;">No products configured. Add one below.</td></tr>`;
                return;
            }
            data.lenders.forEach(l => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${l.name}</strong><br><small style="color:var(--text-muted);">${l.loan_name}</small></td>
                    <td><span class="badge badge-success">${l.loan_type}</span></td>
                    <td style="font-family:var(--font-heading); font-weight:600; color:var(--secondary);">${l.interest_rate}%</td>
                    <td>
                        <div style="font-size:0.75rem; color:var(--text-secondary);">Min Score: ${l.min_credit_score}</div>
                        <div style="font-size:0.75rem; color:var(--text-secondary);">Min Inc: ₹${l.min_income.toLocaleString('en-IN')}</div>
                    </td>
                    <td>
                        <div style="font-size:0.75rem; color:var(--text-secondary);">Fee: ${l.processing_fee_pct}% + ₹${l.flat_processing_fee}</div>
                        <div style="font-size:0.75rem; color:var(--text-secondary);">Ins: ${l.insurance_premium_pct}%</div>
                    </td>
                    <td>
                        <button class="btn btn-outline btn-sm" onclick="editLenderProduct(${l.id})">Edit</button>
                        <button class="btn btn-danger btn-sm" style="margin-left: 0.5rem;" onclick="deleteLenderProduct(${l.id})">Delete</button>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        })
        .catch(err => console.error("Admin load lenders failed:", err));
}

function loadAdminAnalytics() {
    fetch('/api/admin/analytics')
        .then(res => res.json())
        .then(data => {
            document.getElementById("stat-users").innerText = data.total_users;
            document.getElementById("stat-apps").innerText = data.total_applications;
            document.getElementById("stat-cibil").innerText = data.avg_credit_score;
            document.getElementById("stat-amount").innerText = "₹" + Math.round(data.avg_loan_amount).toLocaleString('en-IN');
            document.getElementById("stat-popular").innerText = data.popular_loan_type;
        })
        .catch(err => console.error("Admin load stats failed:", err));
}

window.deleteLenderProduct = function(id) {
    if (!confirm("Are you sure you want to delete this loan product?")) return;
    fetch(`/api/admin/lenders/${id}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            alert(data.message || data.error);
            loadAdminLenders();
            loadAdminAnalytics();
        })
        .catch(err => console.error("Delete failed:", err));
};

window.editLenderProduct = function(id) {
    fetch('/api/admin/lenders')
        .then(res => res.json())
        .then(data => {
            const l = data.lenders.find(item => item.id === id);
            if (!l) return;
            
            const newRate = prompt(`Enter new Interest Rate (p.a.) for ${l.name}:`, l.interest_rate);
            if (newRate === null) return;
            
            l.interest_rate = parseFloat(newRate);
            
            fetch(`/api/admin/lenders/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(l)
            })
            .then(res => res.json())
            .then(data => {
                alert(data.message || data.error);
                loadAdminLenders();
            });
        });
};

function loadAdminUsers() {
    fetch('/api/admin/users')
        .then(res => res.json())
        .then(data => {
            const tableBody = document.getElementById("admin-users-table-body");
            tableBody.innerHTML = "";
            if (!data.users || data.users.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center;">No registered accounts found.</td></tr>`;
                return;
            }
            data.users.forEach(u => {
                const date = new Date(u.created_at).toLocaleDateString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric'
                });
                
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${u.username}</strong></td>
                    <td>${u.email}</td>
                    <td><span class="badge ${u.user_type === 'admin' ? 'badge-danger' : u.user_type === 'first_time' ? 'badge-warning' : 'badge-success'}">${u.user_type}</span></td>
                    <td>${date}</td>
                    <td>
                        <button class="btn btn-outline btn-sm" onclick="editUserLevel(${u.id}, '${u.user_type}')">${translations[currentLang].btn_change_type || 'Change Level'}</button>
                        <button class="btn btn-danger btn-sm" style="margin-left: 0.5rem;" onclick="deleteUserAccount(${u.id})">${translations[currentLang].btn_delete || 'Delete'}</button>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        })
        .catch(err => console.error("Admin load users failed:", err));
}

window.deleteUserAccount = function(id) {
    if (!confirm("Are you sure you want to delete this user profile?")) return;
    fetch(`/api/admin/users/${id}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            alert(data.message || data.error);
            loadAdminUsers();
            loadAdminAnalytics();
        })
        .catch(err => console.error("Delete user failed:", err));
};

window.editUserLevel = function(id, currentType) {
    const newType = prompt("Enter new user level (guest, registered, first_time, admin):", currentType);
    if (!newType) return;
    fetch(`/api/admin/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_type: newType.trim() })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message || data.error);
        loadAdminUsers();
        checkAuth();
    })
    .catch(err => console.error("Edit user level failed:", err));
};
