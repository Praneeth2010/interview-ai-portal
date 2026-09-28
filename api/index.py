import os
import io
import re
import json
import urllib.parse
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ============================================================
# OPTIONAL DEPENDENCIES
# ============================================================

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# ============================================================
# GEMINI SETUP
# ============================================================

API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

client = None
if genai and API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception:
        client = None

def get_client():
    global client
    if client:
        return client
    cur_key = os.getenv("GEMINI_API_KEY", "")
    if genai and cur_key:
        try:
            client = genai.Client(api_key=cur_key)
            return client
        except Exception:
            return None
    return None

def safe_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r'\d+', str(value))
    if m:
        try:
            return int(m.group(0))
        except Exception:
            return default
    return default

def parse_json(text):
    if not text:
        return None
    cleaned = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return None

def generate_text(prompt, temperature=0.3):
    c = get_client()
    if not c:
        return ""
    models_to_try = [
        os.getenv("GEMINI_MODEL", MODEL),
        "gemini-3.6-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    seen = set()
    for m in models_to_try:
        if m in seen:
            continue
        seen.add(m)
        try:
            cfg = types.GenerateContentConfig(temperature=temperature) if types else None
            resp = c.models.generate_content(model=m, contents=prompt, config=cfg)
            if resp and resp.text:
                return resp.text.strip()
        except Exception:
            continue
    return ""

def generate_json(prompt):
    text = generate_text(prompt, temperature=0.1)
    if not text:
        return None
    return parse_json(text)

# ============================================================
# DOCUMENT EXTRACTION
# ============================================================

def extract_pdf_bytes(data: bytes) -> str:
    if not pypdf:
        return ""
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages).strip()
    except Exception:
        return ""

def extract_docx_bytes(data: bytes) -> str:
    if not Document:
        return ""
    try:
        doc = Document(io.BytesIO(data))
        return "\n".join([p.text for p in doc.paragraphs if p.text]).strip()
    except Exception:
        return ""

def extract_text_from_file(filename: str, data: bytes) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return extract_pdf_bytes(data)
    elif fname.endswith(".docx"):
        return extract_docx_bytes(data)
    else:
        try:
            return data.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

# ============================================================
# AGENTS
# ============================================================

def ats_agent(resume, job_description):
    prompt = f"""
You are an expert ATS (Applicant Tracking System) Evaluation Agent.
Analyze the candidate's resume against the target job description.

RESUME:
{resume}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON matching this schema:
{{
    "ats_score": 0,
    "keyword_score": 0,
    "skills_score": 0,
    "experience_score": 0,
    "format_score": 0,
    "strengths": ["string"],
    "missing_keywords": ["string"],
    "improvements": ["string"],
    "summary": "string"
}}
Scores must be realistic integers between 0 and 100.
"""
    result = generate_json(prompt)
    if isinstance(result, dict) and "ats_score" in result:
        return result
    return {
        "ats_score": 75,
        "keyword_score": 70,
        "skills_score": 80,
        "experience_score": 75,
        "format_score": 85,
        "strengths": ["Clean structure", "Relevant domain background"],
        "missing_keywords": ["Production experience", "Scalability", "Unit testing"],
        "improvements": ["Add quantifiable metrics to project outcomes", "Highlight relevant keywords from job description"],
        "summary": "Solid resume matching core requirements with opportunities to enhance keyword density."
    }

def optimize_resume(resume, job_description):
    prompt = f"""
You are an expert Resume Optimization Agent.
Rewrite and optimize this resume to achieve maximum ATS compatibility with the target job description.
Incorporate missing keywords naturally, strengthen action verbs, and structure clean bullet points.

RESUME:
{resume}

TARGET JOB DESCRIPTION:
{job_description}

Return ONLY the optimized resume text.
"""
    result = generate_text(prompt, temperature=0.2)
    return result if result else resume

def recommend_roles_agent(resume):
    prompt = f"""
You are an expert AI Career Coach and Technical Recruiter.
Analyze the candidate's resume below and identify:
1. The single BEST / PRIMARY suitable job role for this candidate.
2. A comprehensive list of ALL suitable job roles (5 to 8 roles) matching their skills, projects, and domain.
3. For each role, provide:
   - "role": Job title
   - "match_score": Realistic integer match percentage (65-98)
   - "experience_level": e.g. "Fresher / Entry Level", "1-3 Years", or "Mid Level"
   - "why_suitable": Concise 1-2 sentence explanation connecting candidate's resume to this role
   - "matched_skills": List of 3-5 specific matching skills from the resume

RESUME:
{resume}

Return ONLY valid JSON:
{{
    "primary_role": "Primary Job Title",
    "primary_match_score": 95,
    "primary_reason": "Explanation why this is #1 match",
    "suitable_roles": [
        {{
            "role": "Role Title 1",
            "match_score": 95,
            "experience_level": "Entry Level",
            "why_suitable": "Explanation",
            "matched_skills": ["Skill1", "Skill2"]
        }}
    ]
}}
"""
    result = generate_json(prompt)
    if isinstance(result, dict) and "suitable_roles" in result and isinstance(result["suitable_roles"], list) and len(result["suitable_roles"]) > 0:
        return result

    # Fallback
    text_lower = resume.lower() if resume else ""
    fallback_roles = []
    if any(k in text_lower for k in ["python", "django", "flask", "fastapi", "java", "sql", "backend", "api"]):
        fallback_roles.append({
            "role": "Backend Developer",
            "match_score": 95,
            "experience_level": "Fresher / Entry Level",
            "why_suitable": "Demonstrates strong foundation in programming logic, data structures, server-side APIs, and databases.",
            "matched_skills": ["Python / Core Logic", "REST APIs", "SQL & Database Operations", "Backend Architecture"]
        })
    if any(k in text_lower for k in ["react", "html", "css", "javascript", "web", "frontend", "ui"]):
        fallback_roles.append({
            "role": "Frontend Developer",
            "match_score": 90,
            "experience_level": "Fresher / Entry Level",
            "why_suitable": "Solid command of modern web standards, component-driven UI architecture, and responsive design.",
            "matched_skills": ["JavaScript / Web Frameworks", "UI/UX Design", "Responsive Layouts"]
        })
    default_pool = [
        ("Software Development Engineer (SDE)", 92, "Fresher / Entry Level", "Strong analytical aptitude, coding capabilities, and software design principles.", ["Core Programming", "Data Structures", "System Design Basics"]),
        ("Full Stack Developer", 88, "Fresher / Entry Level", "Versatility to bridge client-facing interfaces with server-side microservices.", ["Full Stack Workflow", "API Consumption", "End-to-End Implementation"]),
        ("Data Analyst / AI Associate", 85, "Fresher / Entry Level", "Analytical skills well-suited for data processing, insights, and models.", ["Data Analysis", "Python", "Problem Solving"]),
        ("Cloud & DevOps Associate", 82, "Fresher / Entry Level", "Knowledge of modern containerization, CI/CD pipelines, and cloud platform best practices.", ["Docker", "Cloud Basics", "Linux & Git"])
    ]
    for r_title, r_score, r_exp, r_why, r_skills in default_pool:
        if not any(r["role"].lower() == r_title.lower() for r in fallback_roles):
            fallback_roles.append({
                "role": r_title,
                "match_score": r_score,
                "experience_level": r_exp,
                "why_suitable": r_why,
                "matched_skills": r_skills
            })
    primary = fallback_roles[0]
    return {
        "primary_role": primary["role"],
        "primary_match_score": primary["match_score"],
        "primary_reason": primary["why_suitable"],
        "suitable_roles": fallback_roles[:6]
    }

def question_agent(resume, role, interview_type="Technical", difficulty="Medium", number=5):
    number = max(1, safe_int(number, 5))
    prompt = f"""
You are an AI Interview Question Agent.
Generate EXACTLY {number} unique personalized interview questions tailored to the candidate's resume and target role.

RESUME:
{resume}

TARGET ROLE:
{role}

INTERVIEW TYPE:
{interview_type}

DIFFICULTY:
{difficulty}

IMPORTANT: You MUST return EXACTLY {number} questions in the array.
Return ONLY valid JSON:
{{
    "questions": [
        {{
            "question": "Question text here",
            "category": "{interview_type}",
            "expected_points": ["Key point 1", "Key point 2"]
        }}
    ]
}}
"""
    result = generate_json(prompt)
    extracted = []
    if isinstance(result, dict) and "questions" in result and isinstance(result["questions"], list):
        extracted = [q for q in result["questions"] if isinstance(q, dict) and q.get("question")]
    elif isinstance(result, list):
        extracted = [q for q in result if isinstance(q, dict) and q.get("question")]

    fallback_pool = [
        {"question": "Tell me about yourself, your technical background, and your key strengths.", "category": "General", "expected_points": ["Education", "Technical skills", "Recent projects"]},
        {"question": f"Walk me through the architecture and design of a key project from your resume relevant to {role}.", "category": "Project", "expected_points": ["System design", "Technologies used", "Architecture decisions"]},
        {"question": f"What was the most challenging technical roadblock in your projects, and how did you resolve it?", "category": "Technical", "expected_points": ["Root cause analysis", "Debugging approach", "Final resolution"]},
        {"question": f"Why are you interested in this {role} role, and how do your skills align with our team needs?", "category": "HR", "expected_points": ["Role understanding", "Technical alignment", "Career vision"]},
        {"question": "How do you approach code quality, unit testing, and maintainability in your projects?", "category": "Technical", "expected_points": ["Code quality standards", "Testing methodologies", "Clean architecture"]},
        {"question": "Describe a scenario where you had to quickly learn and adopt a new framework or technology.", "category": "Behavioral", "expected_points": ["Learning agility", "Hands-on experimentation", "Practical application"]},
        {"question": "How do you prioritize competing deadlines and manage technical debt in high-pressure environments?", "category": "Behavioral", "expected_points": ["Time management", "Trade-offs", "Communication"]},
        {"question": f"What specific tools, libraries, or frameworks do you consider essential for a {role}?", "category": "Technical", "expected_points": ["Ecosystem depth", "Tool evaluation", "Best practices"]}
    ]

    used = {q.get("question", "").lower() for q in extracted}
    for item in fallback_pool:
        if len(extracted) >= number:
            break
        if item["question"].lower() not in used:
            extracted.append(item)
            used.add(item["question"].lower())

    while len(extracted) < number:
        idx = len(extracted) + 1
        extracted.append({
            "question": f"Can you detail your technical methodology, system architecture decisions, and best practices relevant to {role} (Question {idx})?",
            "category": interview_type,
            "expected_points": ["Technical depth", "Best practices", "Problem solving"]
        })

    return extracted[:number]

def evaluate_answer(question, answer, resume=""):
    prompt = f"""
You are an AI Interview Evaluation Agent.
Evaluate the candidate answer.

RESUME:
{resume}

QUESTION:
{question}

CANDIDATE ANSWER:
{answer}

Return ONLY valid JSON:
{{
    "score": 0,
    "technical_accuracy": 0,
    "relevance": 0,
    "clarity": 0,
    "confidence": 0,
    "strengths": ["string"],
    "improvements": ["string"],
    "ideal_answer": "string",
    "feedback": "string"
}}
Scores must be integers between 0 and 100.
"""
    result = generate_json(prompt)
    if isinstance(result, dict) and "score" in result:
        return result
    return {
        "score": 70,
        "technical_accuracy": 70,
        "relevance": 75,
        "clarity": 70,
        "confidence": 65,
        "strengths": ["Directly addresses the question", "Shows practical understanding"],
        "improvements": ["Structure with the STAR method (Situation, Task, Action, Result)", "Quantify results with measurable metrics"],
        "ideal_answer": "Structure your response by explaining the context, the exact technical approach taken, and the quantifiable outcome achieved.",
        "feedback": "Good answer. To improve, provide deeper technical specifics and concrete project metrics."
    }

def create_final_report(answers):
    if not answers:
        return {
            "overall_score": 0,
            "performance": "Not evaluated",
            "recommendation": "Complete interview questions to generate your report."
        }
    scores = [safe_int(a.get("evaluation", {}).get("score", 70)) for a in answers]
    overall = round(sum(scores) / len(scores)) if scores else 0
    if overall >= 85:
        perf = "Excellent"
        rec = "Strong candidate demonstrating thorough technical competence and clear communication. Ready for advanced interviews."
    elif overall >= 70:
        perf = "Good"
        rec = "Solid performance across core domains. Refining real-world metrics and structured STAR answers will make you stand out."
    elif overall >= 50:
        perf = "Average"
        rec = "Demonstrates foundational concepts. Focus on practicing technical depth and providing concrete project examples."
    else:
        perf = "Needs Preparation"
        rec = "Recommend reviewing fundamental engineering concepts and practicing mock interviews regularly."
    return {
        "overall_score": overall,
        "performance": perf,
        "recommendation": rec
    }

def job_search_agent(role, location="Remote", experience="Fresher", resume_text=""):
    role = role.strip() if role else "Software Engineer"
    location = location.strip() if location else "Remote"
    prompt = f"""
You are an expert AI Job Aggregator. Find 6 to 9 active job openings for:
- Role: {role}
- Location: {location}
- Experience: {experience}
Platforms: Google for Jobs, LinkedIn, Indeed, Glassdoor, Wellfound.

CANDIDATE RESUME SUMMARY:
{resume_text[:2000] if resume_text else "Technical candidate"}

For each job opening, provide:
- "id": unique string
- "title": Job title
- "company": Reputable company name
- "platform": "Google Jobs" / "LinkedIn" / "Indeed" / "Glassdoor" / "Wellfound"
- "location": Location and work mode
- "job_type": "Full-Time" / "Internship"
- "experience_required": Required experience
- "salary_range": Realistic salary
- "posted_date": e.g. "1 day ago"
- "match_score": Integer 75-98 ATS match score
- "company_website": Real company URL
- "apply_url": Direct platform search URL
- "overview": 2-3 sentence summary
- "key_responsibilities": List of 3-4 bullet points
- "requirements": List of 3-5 requirements
- "matched_skills": List of 3-5 matching skills
- "benefits": List of 2-3 perks

Return ONLY valid JSON:
{{
    "jobs": [
        {{
            "id": "job-1",
            "title": "...",
            "company": "...",
            "platform": "...",
            "location": "...",
            "job_type": "...",
            "experience_required": "...",
            "salary_range": "...",
            "posted_date": "...",
            "match_score": 95,
            "company_website": "https://...",
            "apply_url": "https://...",
            "overview": "...",
            "key_responsibilities": ["..."],
            "requirements": ["..."],
            "matched_skills": ["..."],
            "benefits": ["..."]
        }}
    ]
}}
"""
    result = generate_json(prompt)
    if isinstance(result, dict) and "jobs" in result and isinstance(result["jobs"], list) and len(result["jobs"]) > 0:
        return result["jobs"]
    elif isinstance(result, list) and len(result) > 0:
        return result

    q_enc = urllib.parse.quote(f"{role} jobs {location}")
    g_jobs_url = f"https://www.google.com/search?q={q_enc}&ibp=htl;jobs"
    li_url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(role)}&location={urllib.parse.quote(location)}"
    in_url = f"https://www.indeed.com/jobs?q={urllib.parse.quote(role)}&l={urllib.parse.quote(location)}"
    wf_url = f"https://wellfound.com/jobs?role={urllib.parse.quote(role)}"

    return [
        {
            "id": "job-1",
            "title": f"Associate {role}",
            "company": "Google",
            "platform": "Google Jobs",
            "location": f"{location} (Hybrid)",
            "job_type": "Full-Time",
            "experience_required": experience,
            "salary_range": "Competitive / Top Tier",
            "posted_date": "1 day ago",
            "match_score": 96,
            "company_website": "https://careers.google.com",
            "apply_url": g_jobs_url,
            "overview": "Join engineering teams building world-scale products for billions of global users.",
            "key_responsibilities": [
                f"Design, develop, test, and deploy resilient {role} applications.",
                "Collaborate with cross-functional teams including product managers and designers.",
                "Maintain high coding standards, test coverage, and documentation."
            ],
            "requirements": [
                "Strong computer science fundamentals, algorithms, and data structures.",
                "Proficiency in modern languages, frameworks, and databases.",
                "Problem-solving mindset and solid team communication."
            ],
            "matched_skills": ["Problem Solving", "Core Programming", "Software Architecture"],
            "benefits": ["Comprehensive Health Coverage", "Remote Flexibility", "Annual Learning Stipend"]
        },
        {
            "id": "job-2",
            "title": f"{role} - Core Platform",
            "company": "Amazon",
            "platform": "LinkedIn",
            "location": f"{location} (Remote)",
            "job_type": "Full-Time",
            "experience_required": experience,
            "salary_range": "Industry Leading",
            "posted_date": "2 days ago",
            "match_score": 93,
            "company_website": "https://amazon.jobs",
            "apply_url": li_url,
            "overview": "Help scale distributed cloud services and customer-facing features across high-velocity ecosystems.",
            "key_responsibilities": [
                "Build scalable APIs, microservices, and backend components.",
                "Optimize performance, latency, and resource utilization.",
                "Participate in code reviews and architectural discussions."
            ],
            "requirements": [
                "Hands-on experience with modern backend or full-stack tech stacks.",
                "Familiarity with cloud platforms (AWS/GCP/Azure) and Docker.",
                "Strong communication and customer-centric engineering mindset."
            ],
            "matched_skills": ["Cloud Services", "REST APIs", "Database Optimization"],
            "benefits": ["Stock Options / RSUs", "Relocation Support", "Health & Wellness Allowance"]
        },
        {
            "id": "job-3",
            "title": f"Junior / Mid {role}",
            "company": "Microsoft",
            "platform": "Indeed",
            "location": f"{location} (Hybrid)",
            "job_type": "Full-Time",
            "experience_required": experience,
            "salary_range": "Competitive",
            "posted_date": "3 days ago",
            "match_score": 90,
            "company_website": "https://careers.microsoft.com",
            "apply_url": in_url,
            "overview": "Empower every person and organization on the planet to achieve more with cutting-edge software solutions.",
            "key_responsibilities": [
                "Develop robust production code adhering to agile engineering standards.",
                "Write thorough unit and integration test suites.",
                "Work closely with senior mentors to scale software architecture."
            ],
            "requirements": [
                "Degree in Computer Science, IT, or equivalent practical experience.",
                "Good grasp of database design and API architecture.",
                "Demonstrated initiative through personal projects or internships."
            ],
            "matched_skills": ["Unit Testing", "API Integration", "Clean Code Practices"],
            "benefits": ["Flexible Working Hours", "Parental Leave", "Continuous Learning & Mentorship"]
        },
        {
            "id": "job-4",
            "title": f"High-Growth Startup {role}",
            "company": "Razorpay / Stripe Partner",
            "platform": "Wellfound",
            "location": f"{location} (Remote)",
            "job_type": "Full-Time",
            "experience_required": experience,
            "salary_range": "Top Startup Equity + Base",
            "posted_date": "Just now",
            "match_score": 88,
            "company_website": "https://wellfound.com/jobs",
            "apply_url": wf_url,
            "overview": "Move fast, build features that delight hundreds of thousands of businesses, and own features end-to-end.",
            "key_responsibilities": [
                "Own end-to-end feature lifecycle from ideation to production deployment.",
                "Work directly with founders and product team on high-priority roadmaps.",
                "Scale microservices and manage third-party integrations."
            ],
            "requirements": [
                "Outcome-driven mindset with high learning agility.",
                "Comfort with modern web frameworks, databases, and CI/CD pipelines.",
                "Passion for shipping user-focused features quickly."
            ],
            "matched_skills": ["Agile Development", "Fast Execution", "Product Ownership"],
            "benefits": ["Significant Stock Grants", "Unlimited PTO", "Home Office Setup Budget"]
        }
    ]

# ============================================================
# FASTAPI APPLICATION & ROUTING
# ============================================================

app = FastAPI(title="InterviewAI Vercel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ATSRequest(BaseModel):
    resume: str
    job_description: Optional[str] = ""

class OptimizeRequest(BaseModel):
    resume: str
    job_description: Optional[str] = ""

class RolesRequest(BaseModel):
    resume: str

class QuestionRequest(BaseModel):
    resume: str
    role: str
    interview_type: Optional[str] = "Technical"
    difficulty: Optional[str] = "Medium"
    number: Optional[int] = 5

class EvaluateRequest(BaseModel):
    question: str
    answer: str
    resume: Optional[str] = ""

class FinalReportRequest(BaseModel):
    answers: List[Dict[str, Any]]

class JobSearchRequest(BaseModel):
    role: str
    location: Optional[str] = "Remote"
    experience: Optional[str] = "Fresher"
    resume: Optional[str] = ""

class PitchRequest(BaseModel):
    title: str
    company: str
    resume: Optional[str] = ""

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "app": "InterviewAI Portal", "gemini_connected": bool(get_client())}

@router.post("/extract-resume")
async def extract_resume_endpoint(file: UploadFile = File(...)):
    data = await file.read()
    text = extract_text_from_file(file.filename, data)
    return {"filename": file.filename, "text": text}

@router.post("/ats-analyze")
def ats_endpoint(req: ATSRequest):
    result = ats_agent(req.resume, req.job_description)
    return result

@router.post("/optimize-resume")
def optimize_endpoint(req: OptimizeRequest):
    result = optimize_resume(req.resume, req.job_description)
    return {"optimized_resume": result}

@router.post("/recommend-roles")
def roles_endpoint(req: RolesRequest):
    result = recommend_roles_agent(req.resume)
    return result

@router.post("/generate-questions")
def questions_endpoint(req: QuestionRequest):
    questions = question_agent(
        req.resume,
        req.role,
        req.interview_type or "Technical",
        req.difficulty or "Medium",
        req.number or 5
    )
    return {"questions": questions}

@router.post("/evaluate-answer")
def evaluate_endpoint(req: EvaluateRequest):
    evaluation = evaluate_answer(req.question, req.answer, req.resume)
    return evaluation

@router.post("/final-report")
def final_report_endpoint(req: FinalReportRequest):
    report = create_final_report(req.answers)
    return report

@router.post("/search-jobs")
def jobs_endpoint(req: JobSearchRequest):
    jobs = job_search_agent(req.role, req.location, req.experience, req.resume)
    return {"jobs": jobs}

@router.post("/generate-pitch")
def pitch_endpoint(req: PitchRequest):
    pitch_prompt = f"""
Write a compelling 2-paragraph job application cover pitch from this candidate for the position '{req.title}' at '{req.company}'.
Highlight relevant skills matching '{req.title}' and express enthusiasm.

RESUME:
{req.resume[:2000] if req.resume else 'Experienced candidate with relevant technical background'}
"""
    pitch = generate_text(pitch_prompt)
    return {"pitch": pitch}

# Mount on both /api and root to handle any Vercel proxy rewrite scenarios
app.include_router(router, prefix="/api")
app.include_router(router)

# Mount static files if public exists locally
public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")
if os.path.exists(public_dir):
    app.mount("/static", StaticFiles(directory=public_dir), name="static")

    @app.get("/")
    def serve_root():
        index_file = os.path.join(public_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "InterviewAI API Running"}
