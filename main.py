from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func, desc, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone
from typing import List, Optional
from fastapi.responses import RedirectResponse, HTMLResponse, Response
import uuid
import os
from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, auth, firestore
import random

firestore_db = None
# Initialize Firebase Admin SDK (with graceful fallback for hackathon mock testing)
try:
    if not firebase_admin._apps:
        # Assuming you will place your JSON file in the project root
        cred = credentials.Certificate("firebase-adminsdk.json")
        firebase_admin.initialize_app(cred)
    firestore_db = firestore.client()
    FIREBASE_ENABLED = True
except Exception as e:
    print(f"Warning: Firebase Admin SDK not initialized. Mock mode active. Error details: {e}")
    FIREBASE_ENABLED = False

from google import genai
ai_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Switch to v3 database for new RBAC and identity schema
SQLALCHEMY_DATABASE_URL = "sqlite:///./civicpulse_v3.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    jansetu_id = Column(String, unique=True, index=True)
    full_name = Column(String)
    phone = Column(String)
    id_type = Column(String)
    id_number = Column(String)
    role = Column(String)

class GrievanceDB(Base):
    __tablename__ = "grievances"
    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String, unique=True, index=True)
    citizen_name = Column(String, index=True)
    location = Column(String, index=True)
    raw_text = Column(String)
    id_type = Column(String)
    id_number_masked = Column(String)
    is_student = Column(Boolean, default=False)
    college_name = Column(String, nullable=True)
    student_id = Column(String, nullable=True)
    category = Column(String, index=True)
    urgency_score = Column(Integer)
    ai_summary = Column(String)
    citizen_impact_count = Column(Integer, default=1)
    status = Column(String, default="Received")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JanSetu API", description="Enterprise-grade Civic Governance Platform")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

templates = Jinja2Templates(directory="templates")
# Disable Jinja2 internal caching (prevents unhashable dict errors with complex context)
templates.env.cache = {}

class GrievanceAnalysis(BaseModel):
    category: str
    urgency_score: int
    ai_summary: str

def analyze_grievance(raw_text: str) -> GrievanceAnalysis:
    prompt = f"Analyze the following civic grievance. Determine the category (e.g., 'Road Infrastructure', 'Water Supply', 'Electricity', 'Sanitation'), assign an urgency score from 1 to 5 (5 being critical/safety hazard), and provide a 1-sentence ai_summary.\n\nGrievance: {raw_text}"
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': GrievanceAnalysis, 'temperature': 0.1}
        )
        return response.parsed
    except Exception as e:
        print("AI generation failed, using fallback:", e)
        return GrievanceAnalysis(
            category="Civic Issue",
            urgency_score=3,
            ai_summary="AI Analysis Temporarily Unavailable. Manual review required for this submission."
        )

class MemoRequest(BaseModel):
    location: str

class GrievanceCreate(BaseModel):
    citizen_name: str
    location: str
    raw_text: str
    id_type: str
    id_number: str
    is_student: bool = False
    college_name: Optional[str] = None
    student_id: Optional[str] = None

class GrievanceResponse(BaseModel):
    id: int
    reference_id: str
    citizen_name: str
    location: str
    raw_text: str
    category: str
    urgency_score: int
    ai_summary: str
    citizen_impact_count: int
    status: str
    timestamp: datetime
    id_type: Optional[str] = None
    id_number_masked: Optional[str] = None
    is_student: Optional[bool] = False
    college_name: Optional[str] = None
    student_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return RedirectResponse(url="/citizen")

@app.get("/citizen", response_class=HTMLResponse)
def get_citizen(request: Request, db: Session = Depends(get_db)):
    jansetu_id = request.cookies.get("jansetu_id")
    my_grievances = []
    user_name = "Citizen"
    
    # In SQLite, we store the ID in id_number_masked if it was submitted by an authenticated user
    if jansetu_id:
        local_user = db.query(UserDB).filter(UserDB.jansetu_id == jansetu_id).first()
        if local_user:
            user_name = local_user.full_name
        my_g_raw = db.query(GrievanceDB).filter(GrievanceDB.id_number_masked == jansetu_id).order_by(desc(GrievanceDB.timestamp)).all()
        for g in my_g_raw:
            g_dict = g.__dict__.copy()
            if isinstance(g.timestamp, str):
                g_dict['date_str'] = g.timestamp[:10]
            else:
                g_dict['date_str'] = g.timestamp.strftime('%Y-%m-%d') if g.timestamp else "N/A"
            my_grievances.append(g_dict)
        
    # Fetch resolved/progress grievances for public transparency (without IDs)
    public_feed_raw = db.query(GrievanceDB).filter(
        GrievanceDB.status.in_(["Resolved", "Resolution In Progress"])
    ).order_by(desc(GrievanceDB.timestamp)).limit(10).all()
    
    public_feed = []
    for f in public_feed_raw:
        f_dict = f.__dict__.copy()
        if isinstance(f.timestamp, str):
            try:
                dt = datetime.fromisoformat(f.timestamp)
                f_dict['date_str'] = dt.strftime('%d %b %Y')
            except:
                f_dict['date_str'] = f.timestamp[:10]
        else:
            f_dict['date_str'] = f.timestamp.strftime('%d %b %Y') if f.timestamp else "N/A"
        public_feed.append(f_dict)
        
    return templates.TemplateResponse(request=request, name="citizen.html", context={
        "request": request, 
        "jansetu_id": jansetu_id,
        "user_name": user_name,
        "my_grievances": my_grievances,
        "public_feed": public_feed
    })

@app.get("/login", response_class=HTMLResponse)
def get_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.get("/register", response_class=HTMLResponse)
def get_register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={"request": request})

@app.post("/register")
def register_user(full_name: str = Form(...), phone: str = Form(...), id_type: str = Form(...), id_number: str = Form(...), db: Session = Depends(get_db)):
    user_id = f"JS-USR-{random.randint(1000, 9999)}"
    is_student = (id_type == 'Student ID')
    user_data = {
        "jansetu_id": user_id,
        "full_name": full_name,
        "phone": phone,
        "id_type": id_type,
        "id_number": id_number,
        "role": "student" if is_student else "citizen"
    }
    
    # 1. Save to SQLite (Local Fallback for Hackathon)
    db_user = UserDB(**user_data)
    db.add(db_user)
    db.commit()
    
    # 2. Attempt Save to Firestore (Cloud Production)
    if FIREBASE_ENABLED and firestore_db:
        try:
            firestore_db.collection("users").document(user_id).set(user_data)
        except Exception as e:
            print("Firestore save failed (Database might not be created in console), using SQLite fallback. Error:", e)
            
    # Instead of creating a whole new page, we can just render the citizen dashboard instantly, or show an alert
    response = RedirectResponse(url="/citizen", status_code=303)
    # In a real app we'd show the ID, for hackathon let's just log them in directly
    response.set_cookie(key="session_role", value=user_data["role"])
    response.set_cookie(key="jansetu_id", value=user_id)
    return response

@app.post("/login")
def login(phone: str = Form(...), role: str = Form(...), token: str = Form(...), db: Session = Depends(get_db)):
    # phone can be either a JanSetu ID (JS-USR-XXXX) or a phone number for officials
    clean_val = phone.replace(" ", "")
    
    # 1. Master Admin Hardcode bypass
    if clean_val == "+919999999999" or clean_val == "+918073749895":
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_role", value="owner")
        return response
        
    # 2. Public Portal Login (Checking JanSetu ID)
    if clean_val.startswith("JS-USR-"):
        actual_role = "citizen"
        user_found = False
        
        # Check SQLite first (Hybrid mode)
        local_user = db.query(UserDB).filter(UserDB.jansetu_id == clean_val).first()
        if local_user:
            actual_role = local_user.role
            user_found = True
            
        # Check Firestore if enabled
        if not user_found and FIREBASE_ENABLED and firestore_db:
            try:
                user_doc = firestore_db.collection("users").document(clean_val).get()
                if user_doc.exists:
                    actual_role = user_doc.to_dict().get("role", "citizen")
                    user_found = True
            except Exception as e:
                pass 
                
        if not user_found:
            raise HTTPException(status_code=401, detail="Invalid JanSetu ID. Please register first.")
            
        response = RedirectResponse(url="/citizen", status_code=303)
        response.set_cookie(key="session_role", value=actual_role)
        response.set_cookie(key="jansetu_id", value=clean_val)
        return response

    # 3. Government Official Login
    if FIREBASE_ENABLED and firestore_db:
        try:
            # Check if this phone is authorized
            off_doc = firestore_db.collection("authorized_officials").document(clean_val).get()
            if not off_doc.exists:
                # For hackathon demo, if not found, we just let them in as official anyway to not block the demo
                pass
        except:
            pass

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_role", value="official")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_role")
    return response

def verify_admin(request: Request):
    role = request.cookies.get("session_role")
    if role not in ["official", "owner"]:
        raise HTTPException(status_code=401, detail="Unauthorized. Government access only.")

# --- FRONTEND ROUTES ---
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(request: Request, db: Session = Depends(get_db), ward: Optional[str] = None):
    if request.cookies.get("session_role") not in ["official", "owner"]:
        return RedirectResponse(url="/login")
    query_total = db.query(func.sum(GrievanceDB.citizen_impact_count))
    query_critical = db.query(GrievanceDB).filter(GrievanceDB.urgency_score >= 4)
    query_priorities = db.query(
        GrievanceDB.location,
        func.sum(GrievanceDB.urgency_score).label("total_urgency"),
        func.sum(GrievanceDB.citizen_impact_count).label("grievance_count")
    )
    query_recent = db.query(GrievanceDB)
    
    if ward:
        query_total = query_total.filter(GrievanceDB.location == ward)
        query_critical = query_critical.filter(GrievanceDB.location == ward)
        query_priorities = query_priorities.filter(GrievanceDB.location == ward)
        query_recent = query_recent.filter(GrievanceDB.location == ward)
        
    total = query_total.scalar() or 0
    critical = query_critical.count()
    wards = db.query(GrievanceDB.location).distinct().count()
    all_wards = [w[0] for w in db.query(GrievanceDB.location).distinct().all()]
    
    priorities = query_priorities.group_by(GrievanceDB.location).all()
    
    hotspots = []
    for loc, tot_urg, count in priorities:
        hotspots.append({"location": loc, "score": (tot_urg or 0) * (count or 1), "count": count})
    hotspots.sort(key=lambda x: x["score"], reverse=True)
    
    recent = query_recent.order_by(desc(GrievanceDB.timestamp)).limit(10).all()
    
    # Format timestamps safely for the dashboard
    recent_formatted = []
    for r in recent:
        r_dict = r.__dict__.copy()
        if isinstance(r.timestamp, str):
            try:
                dt = datetime.fromisoformat(r.timestamp)
                r_dict['date_str'] = dt.strftime('%A, %b %d')
                r_dict['time_str'] = dt.strftime('%I:%M %p UTC')
            except:
                r_dict['date_str'] = r.timestamp[:10]
                r_dict['time_str'] = r.timestamp[11:16]
        else:
            r_dict['date_str'] = r.timestamp.strftime('%A, %b %d') if r.timestamp else "N/A"
            r_dict['time_str'] = r.timestamp.strftime('%I:%M %p UTC') if r.timestamp else "N/A"
        recent_formatted.append(r_dict)
        
    # 1. Fetch from SQLite
    registered_users = []
    local_users = db.query(UserDB).all()
    for lu in local_users:
        registered_users.append({
            "jansetu_id": lu.jansetu_id,
            "full_name": lu.full_name,
            "phone": lu.phone,
            "id_type": lu.id_type,
            "id_number": lu.id_number,
            "role": lu.role
        })
        
    # 2. Fetch from Firestore (merge)
    if FIREBASE_ENABLED and firestore_db:
        try:
            users_ref = firestore_db.collection("users").get()
            for doc in users_ref:
                udata = doc.to_dict()
                if not any(u["jansetu_id"] == udata["jansetu_id"] for u in registered_users):
                    registered_users.append(udata)
        except:
            pass
            
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "total": total,
            "critical": critical,
            "wards": wards,
            "hotspots": hotspots,
            "recent": recent_formatted,
            "all_wards": all_wards,
            "selected_ward": ward,
            "registered_users": registered_users
        }
    )

@app.get("/tracker", response_class=HTMLResponse)
def get_tracker(request: Request, ref: Optional[str] = None, db: Session = Depends(get_db)):
    grievance = None
    if ref:
        grievance = db.query(GrievanceDB).filter(GrievanceDB.reference_id == ref).first()
    return templates.TemplateResponse(request=request, name="tracker.html", context={"request": request, "grievance": grievance, "ref": ref})


# --- API ROUTES ---
@app.post("/api/grievances", response_model=GrievanceResponse)
def create_grievance(grievance: GrievanceCreate, db: Session = Depends(get_db)):
    # 1. AI Parsing
    try:
        analysis = analyze_grievance(grievance.raw_text)
    except Exception as e:
        # Fallback to rule-based tagging
        text_lower = grievance.raw_text.lower()
        if "pothole" in text_lower or "road" in text_lower:
            cat = "Road Infrastructure"
            score = 4
        elif "water" in text_lower or "pipe" in text_lower:
            cat = "Water Supply"
            score = 3
        elif "electric" in text_lower or "power" in text_lower or "wire" in text_lower:
            cat = "Electricity"
            score = 4
        else:
            cat = "General"
            score = 2
        analysis = GrievanceAnalysis(category=cat, urgency_score=score, ai_summary="Auto-classified by fallback rules due to AI unavailability.")
        
    # 2. (Deduplication engine removed for prototype so every user sees their own submissions in the dashboard)

    # 3. Create new record with tracking ID
    ref_id = f"JS-{str(uuid.uuid4())[:4].upper()}"
    
    # Do not mask if it is a JanSetu ID
    if grievance.id_number.startswith("JS-USR-"):
        masked_id = grievance.id_number
    else:
        masked_id = "X" * max(0, len(grievance.id_number) - 4) + grievance.id_number[-4:] if len(grievance.id_number) >= 4 else "XXXX"
        
    db_grievance = GrievanceDB(
        reference_id=ref_id,
        citizen_name=grievance.citizen_name,
        location=grievance.location,
        raw_text=grievance.raw_text,
        category=analysis.category,
        urgency_score=analysis.urgency_score,
        ai_summary=analysis.ai_summary,
        status="AI Verified",
        id_type=grievance.id_type,
        id_number_masked=masked_id,
        is_student=grievance.is_student,
        college_name=grievance.college_name,
        student_id=grievance.student_id
    )
    db.add(db_grievance)
    db.commit()
    db.refresh(db_grievance)
    return db_grievance

class StatusUpdate(BaseModel):
    status: str

@app.post("/api/grievances/{id}/status")
def update_status(id: int, status_update: StatusUpdate, db: Session = Depends(get_db), admin: None = Depends(verify_admin)):
    grievance = db.query(GrievanceDB).filter(GrievanceDB.id == id).first()
    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")
    grievance.status = status_update.status
    db.commit()
    return {"message": "Status updated successfully", "status": grievance.status}

@app.post("/analytics/generate-memo")
def generate_memo(req: MemoRequest, db: Session = Depends(get_db)):
    issues = db.query(GrievanceDB).filter(GrievanceDB.location == req.location).order_by(desc(GrievanceDB.urgency_score)).limit(10).all()
    if not issues:
        raise HTTPException(status_code=404, detail="No grievances found for this location.")
        
    prompt = f"Draft a formal executive budget allocation memo for the municipal commissioner for the ward '{req.location}'.\n"
    prompt += "Base the recommendations on these high-priority grievances:\n"
    for i in issues:
        prompt += f"- {i.category} (Urgency: {i.urgency_score}): {i.ai_summary} (Impacted: {i.citizen_impact_count})\n"
    prompt += "\nThe memo should be professional, recommend immediate emergency fund distribution to fix these issues. Format beautifully as Markdown."
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return {"memo": response.text}
    except Exception as e:
        return {"memo": f"⚠️ **AI Generation Temporarily Unavailable**\n\nThe AI Policy Memo Generator is currently experiencing high demand. Please try again later.\n\nError details: {str(e)}"}

@app.get("/analytics/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    total = db.query(func.sum(GrievanceDB.citizen_impact_count)).scalar() or 0
    critical = db.query(func.sum(GrievanceDB.citizen_impact_count)).filter(GrievanceDB.urgency_score >= 4).scalar() or 0
    
    # Calculate by category
    categories_query = db.query(
        GrievanceDB.category,
        func.sum(GrievanceDB.citizen_impact_count).label("count")
    ).group_by(GrievanceDB.category).all()
    
    by_category = {cat: (cnt or 0) for cat, cnt in categories_query}
    
    return {
        "total_grievances": total,
        "by_urgency": {
            "Critical (4-5)": critical
        },
        "by_category": by_category
    }

@app.get("/analytics/priorities")
def get_analytics_priorities(db: Session = Depends(get_db)):
    priorities = db.query(
        GrievanceDB.location,
        func.sum(GrievanceDB.urgency_score).label("total_urgency"),
        func.sum(GrievanceDB.citizen_impact_count).label("grievance_count")
    ).group_by(GrievanceDB.location).all()
    
    result = []
    for loc, tot_urg, count in priorities:
        tot_urg = tot_urg or 0
        count = count or 0
        priority_score = tot_urg * (count or 1)
        result.append({
            "location": loc,
            "total_urgency": tot_urg,
            "grievance_count": count,
            "priority_score": priority_score
        })
    
    result.sort(key=lambda x: x["priority_score"], reverse=True)
    return result

@app.get("/api/grievances", response_model=List[GrievanceResponse])
def read_grievances(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(GrievanceDB).offset(skip).limit(limit).all()

@app.get("/api/export")
def export_grievances(db: Session = Depends(get_db)):
    grievances = db.query(GrievanceDB).all()
    
    csv_content = "ID,Reference ID,Citizen Name,Location,Category,Urgency,Impact,Status,Timestamp\n"
    for g in grievances:
        text_safe = g.raw_text.replace(",", ";").replace("\n", " ") if g.raw_text else ""
        csv_content += f"{g.id},{g.reference_id},{g.citizen_name},{g.location},{g.category},{g.urgency_score},{g.citizen_impact_count},{g.status},{g.timestamp}\n"
        
    return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=grievances_audit.csv"})
