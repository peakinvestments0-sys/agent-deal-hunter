# 🎯 AGENT DEAL HUNTER
### Florida Realtor Off-Market & Pocket Listing Deal Desk

A purpose-built acquisition engine modeled after the Pinellas County App to hunt off-market deals directly from licensed listing agents.

---

## ⚡ Quick Start
Double-click `run_app.bat` or run:
```bash
python server.py
```
Open your browser to: **`http://localhost:8001`**

---

## 🚀 Key Features

1. **Propwire CSV Ingestion**:
   - Ingests active listing agents from Propwire exports.
   - De-duplicates listings under unique agent profiles (Phone/Email).
   - Multi-county support (Brevard, Pinellas, Hillsborough, Orange, etc.).

2. **Android SMS Gateway**:
   - Dispatches cellular SMS directly from your Android phone for free.
   - 4 built-in agent outreach templates (Icebreaker, Double Commission, 30-Day Check-in, Backup Cash Offer).

3. **SMTP2GO Email Relay**:
   - Professional HTML offer emails sent directly to the agent's inbox.
   - Built-in commission protection hooks.

4. **"Setup Call" Negotiation Copilot (HUD)**:
   - Instant buy-box calculation (Estimated ARV, Rehab estimate, 15% investor margin, 50–60% target offer range, Formula MAO).
   - Dynamic 5-step call script tailored to the specific property condition and asking price.

5. **1-Click Florida FAR/BAR & LOI Contract Engine (PandaDoc API)**:
   - Pre-fills Buyer Entity (`Peak Investments LLC and/or Assigns`) and Signer (`Johnathan Roberts`).
   - Page 12 automatically preserves the listing agent's brokerage commission.
   - Generates downloadable PDFs or dispatches for e-signature via PandaDoc API with live session links.
