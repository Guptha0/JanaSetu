# 🚀 JanSetu (Prototype)
> **Digital Public Infrastructure for Citizens**

**⚠️ NOTE TO JUDGES & REVIEWERS:** 
*This repository represents a 24-hour **High-Fidelity Prototype** created for a hackathon. It is a proof-of-concept meant to demonstrate the core UI, database routing, and AI triage capabilities. It is **not** a fully completed, production-ready system. Features like real-time SMS OTPs, live GPS maps, and Firebase Cloud Synchronization are stubbed out or simulated for the sake of the demonstration.*

---

## 📖 The Vision
JanSetu ("People's Bridge") is a next-generation civic governance platform designed to bridge the massive communication gap between citizens and municipal policymakers. It solves three major problems:
1.  **Reporting Friction:** Complex, buggy portals discourage citizens from reporting community issues.
2.  **Data Overload:** Governments receive thousands of unstructured complaints but lack the ability to instantly prioritize life-threatening hazards (e.g., live wires) over minor annoyances.
3.  **Lack of Transparency:** Citizens submit forms into a "black box" and never see if the government is actually taking action.

## ✨ Core Features (Working in this Prototype)
*   **Universal Registration:** Supports global identity formats including Passports, Aadhaar, Voter IDs, and Student IDs.
*   **Passwordless Dashboard:** Users log in securely using an anonymized `JanSetu ID` to view a live tracker of "My Submissions".
*   **AI-Powered Triage (Gemini):** Instantly analyzes unstructured citizen complaints to assign a standardized Category and an Urgency Score (1-5).
*   **Executive Admin Dashboard:** Allows policymakers to view localized "Hotspots", track critical hazards, and manually update the status of grievances.
*   **Graceful AI Fallback:** Engineered to never crash during a demo. If the Google Gemini AI API times out, the backend instantly routes the text through a local keyword-scanner to assign the Urgency Score offline.

## 🛠️ Tech Stack
*   **Frontend:** HTML5, Vanilla JS, TailwindCSS, Jinja2
*   **Backend:** Python, FastAPI
*   **Database:** SQLite (SQLAlchemy) - *Used locally to guarantee 100% offline uptime for the hackathon demo.*
*   **AI Integration:** Google GenAI SDK (`gemini-2.5-flash`)

## 🚀 Running Locally
1. Clone this repository:
   ```bash
   git clone https://github.com/Guptha0/JanaSetu.git
   cd JanaSetu
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory and add your Google Gemini API Key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```
4. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```
5. Open your browser to `http://localhost:8000`

## 🗺️ Future Post-Hackathon Roadmap
*   **Cloud Migration:** Transitioning the local SQLite database to Google Firebase Firestore for real-time state-wide cloud sync.
*   **Twilio Integration:** Dispatching automated SMS updates to citizens when an admin updates the status of their grievance.
*   **Geospatial Maps:** Allowing users to drop a pin on a live map instead of manually typing their ward.

---
*Built with ❤️ for the Hackathon.*
