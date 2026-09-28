# 🚀 InterviewAI Portal (Vercel Serverless Edition)

A full-stack, enterprise-grade AI Interview & Career Preparation Platform powered by **Google Gemini 2.5 / 3.0**, **FastAPI**, and modern responsive frontend. Fully architected for **Vercel Serverless** deployment with permanent global hosting (`https://<project-name>.vercel.app`).

---

## ✨ Features

1. **Dashboard & Analytics**: Track ATS readiness, mock interview sessions completed, and average performance scores with local persistence.
2. **Resume & ATS Optimization Agent**:
   - Multi-format resume parsing (`.pdf`, `.docx`, `.txt`).
   - Deep ATS scoring breakdown (Keyword Match, Skills Alignment, Experience Depth, Formatting).
   - Strengths, missing keywords, and actionable suggestions.
   - **1-Click AI Resume Auto-Adjust**: Re-writes resume directly matching target job description.
3. **Smart Suitable Role Recommendation Agent**:
   - Analyzes resume projects, stack, and domain.
   - Identifies the **#1 Top Recommended Job Role** with match percentage and justification.
   - Recommends **All Matching Roles** with customizable direct "Select Role" buttons that immediately pre-fill interview preparation.
4. **Mock Interview Practice Agent**:
   - Dynamic questions tailored to candidate's exact role, difficulty (Easy, Medium, Hard), and interview type (Technical, HR, Behavioral, System Design, Coding).
   - Configurable question counts (3, 5, 8, 10).
   - **Native Text-to-Speech (TTS)**: Automatically reads each question aloud with Play/Replay controls.
   - Real-time AI answer evaluation with score, strengths, and areas to improve.
5. **Real-Time Job Applications Agent**:
   - Live job search matching candidate skills across **Google Jobs, LinkedIn, Indeed, Glassdoor, and Wellfound**.
   - **Option 1: View Website & Job Profile**: Deep-dive into company website, tech stack, and job details.
   - **Option 2: Apply for Job**: Direct application link to career portal or hiring platform.
   - **AI Cover Pitch Generator**: Generates tailored application pitch for each selected job opening.
6. **Final Performance Report**:
   - Overall interview score and comprehensive readiness verdict.
   - Question-by-question review with scores and feedback.

---

## 📁 Project Structure

```
vercel_app/
├── api/
│   └── index.py            # FastAPI ASGI Backend with all 6 Gemini AI Agents
├── public/
│   └── index.html          # High-performance Single Page Application
├── requirements.txt        # Serverless Python dependencies
├── vercel.json             # Vercel Serverless routing configuration
└── README.md
```

---

## 🛠️ Local Development

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Gemini API Key (Optional)
```bash
# Windows PowerShell:
$env:GEMINI_API_KEY="your-gemini-api-key"

# Linux / Mac:
export GEMINI_API_KEY="your-gemini-api-key"
```

### 3. Start Local Server
```bash
python -m uvicorn api.index:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🌐 Deploy to Vercel (Permanent 24/7 Link)

### Option A: 1-Click Deploy via GitHub (Recommended)

1. Push this folder to a GitHub repository:
   ```bash
   cd c:\IntAss\vercel_app
   git init -b main
   git add .
   git commit -m "Initial commit for Vercel deployment"
   # Create a repo on github.com, then:
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```
2. Go to **[vercel.com/new](https://vercel.com/new)** and import your GitHub repository.
3. In **Settings -> Environment Variables**, add:
   - Key: `GEMINI_API_KEY`
   - Value: `your-gemini-api-key`
4. Click **Deploy**. Vercel will give you a permanent URL:
   `https://<your-project-name>.vercel.app`

### Option B: Deploy via Vercel CLI

1. Run the Vercel CLI from inside `vercel_app`:
   ```bash
   cd c:\IntAss\vercel_app
   npx vercel
   ```
2. Follow the terminal prompts (Login, Select Scope, Link to Project).
3. To deploy to production:
   ```bash
   npx vercel --prod
   ```
4. Set the environment variable in Vercel:
   ```bash
   npx vercel env add GEMINI_API_KEY
   ```
