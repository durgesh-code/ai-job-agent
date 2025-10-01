# src/web/app.py
from fastapi import FastAPI, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime

from src.db import SessionLocal, init_db
from src.models import UserProfile, Job, Company, Match, JobApplication, Notification
from src.resume.enhanced_parser import enhanced_parser
from src.matcher.enhanced_matcher import enhanced_matcher
from src.config import config

app = FastAPI(title="AI Job Agent", description="Intelligent Job Matching Platform")

# Static files and templates
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard"""
    # Get or create default user
    user = db.query(UserProfile).first()
    if not user:
        user = UserProfile(name="Default User")
        db.add(user)
        db.commit()
    
    # Get recent matches
    recent_matches = db.query(Match).filter(
        Match.user_id == user.id
    ).order_by(Match.overall_score.desc()).limit(10).all()
    
    # Get job statistics
    total_jobs = db.query(Job).filter(Job.is_active == True).count()
    total_companies = db.query(Company).count()
    applied_jobs = db.query(JobApplication).filter(JobApplication.user_id == user.id).count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "recent_matches": recent_matches,
        "stats": {
            "total_jobs": total_jobs,
            "total_companies": total_companies,
            "applied_jobs": applied_jobs,
            "match_count": len(recent_matches)
        }
    })

@app.get("/jobs", response_class=HTMLResponse)
async def jobs_list(
    request: Request,
    page: int = 1,
    location: Optional[str] = None,
    experience_level: Optional[str] = None,
    remote_option: Optional[str] = None,
    min_salary: Optional[int] = None,
    company_size: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Job listings with filters"""
    per_page = 20
    offset = (page - 1) * per_page
    
    # Build query
    query = db.query(Job).filter(Job.is_active == True)
    
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if experience_level:
        query = query.filter(Job.experience_level == experience_level)
    if remote_option:
        query = query.filter(Job.remote_option == remote_option)
    if min_salary:
        query = query.filter(Job.salary_min >= min_salary)
    if company_size:
        query = query.join(Company).filter(Company.company_size == company_size)
    
    # Get jobs with pagination
    jobs = query.order_by(Job.job_score.desc()).offset(offset).limit(per_page).all()
    total_jobs = query.count()
    
    # Calculate pagination
    total_pages = (total_jobs + per_page - 1) // per_page
    
    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "jobs": jobs,
        "page": page,
        "total_pages": total_pages,
        "filters": {
            "location": location,
            "experience_level": experience_level,
            "remote_option": remote_option,
            "min_salary": min_salary,
            "company_size": company_size
        }
    })

@app.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int, db: Session = Depends(get_db)):
    """Job detail page"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get user's match for this job if exists
    user = db.query(UserProfile).first()
    match = None
    if user:
        match = db.query(Match).filter(
            Match.user_id == user.id,
            Match.job_id == job_id
        ).first()
    
    # Get user's application status
    application = None
    if user:
        application = db.query(JobApplication).filter(
            JobApplication.user_id == user.id,
            JobApplication.job_id == job_id
        ).first()
    
    # Get similar jobs
    similar_jobs = db.query(Job).filter(
        Job.id != job_id,
        Job.is_active == True,
        Job.experience_level == job.experience_level
    ).limit(5).all()
    
    return templates.TemplateResponse("job_detail.html", {
        "request": request,
        "job": job,
        "match": match,
        "application": application,
        "similar_jobs": similar_jobs
    })

@app.get("/companies", response_class=HTMLResponse)
async def companies_list(
    request: Request,
    page: int = 1,
    company_size: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Company listings"""
    per_page = 20
    offset = (page - 1) * per_page
    
    query = db.query(Company)
    
    if company_size:
        query = query.filter(Company.company_size == company_size)
    if location:
        query = query.filter(Company.location.ilike(f"%{location}%"))
    
    companies = query.order_by(Company.company_score.desc()).offset(offset).limit(per_page).all()
    total_companies = query.count()
    total_pages = (total_companies + per_page - 1) // per_page
    
    return templates.TemplateResponse("companies.html", {
        "request": request,
        "companies": companies,
        "page": page,
        "total_pages": total_pages,
        "filters": {
            "company_size": company_size,
            "location": location
        }
    })

@app.get("/company/{company_id}", response_class=HTMLResponse)
async def company_detail(request: Request, company_id: int, db: Session = Depends(get_db)):
    """Company detail page"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Get company jobs
    jobs = db.query(Job).filter(
        Job.company_id == company_id,
        Job.is_active == True
    ).order_by(Job.job_score.desc()).all()
    
    return templates.TemplateResponse("company_detail.html", {
        "request": request,
        "company": company,
        "jobs": jobs
    })

@app.get("/profile", response_class=HTMLResponse)
async def user_profile(request: Request, db: Session = Depends(get_db)):
    """User profile page"""
    user = db.query(UserProfile).first()
    if not user:
        user = UserProfile(name="Default User")
        db.add(user)
        db.commit()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user
    })

@app.post("/profile/upload-resume")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse resume"""
    if not file.filename.endswith(('.pdf', '.docx', '.doc', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    # Save uploaded file temporarily
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Parse resume
        parsed_data = enhanced_parser.parse_resume_file(tmp_path)
        
        # Get or create user
        user = db.query(UserProfile).first()
        if not user:
            user = UserProfile()
            db.add(user)
        
        # Update user profile
        profile_data = enhanced_parser.create_user_profile(parsed_data)
        for key, value in profile_data.items():
            if value is not None:
                setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
        db.commit()
        
        # Trigger job matching
        enhanced_matcher.match_user_to_jobs(user.id)
        
        return RedirectResponse(url="/profile", status_code=303)
        
    finally:
        # Clean up temporary file
        os.unlink(tmp_path)

@app.get("/matches", response_class=HTMLResponse)
async def job_matches(
    request: Request,
    page: int = 1,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Job matches for user"""
    user = db.query(UserProfile).first()
    if not user:
        return RedirectResponse(url="/profile")
    
    per_page = 20
    offset = (page - 1) * per_page
    
    query = db.query(Match).filter(Match.user_id == user.id)
    
    if min_score:
        query = query.filter(Match.overall_score >= min_score)
    
    matches = query.order_by(Match.overall_score.desc()).offset(offset).limit(per_page).all()
    total_matches = query.count()
    total_pages = (total_matches + per_page - 1) // per_page
    
    return templates.TemplateResponse("matches.html", {
        "request": request,
        "matches": matches,
        "page": page,
        "total_pages": total_pages,
        "min_score": min_score
    })

@app.post("/job/{job_id}/apply")
async def apply_to_job(job_id: int, notes: str = Form(""), db: Session = Depends(get_db)):
    """Apply to a job"""
    user = db.query(UserProfile).first()
    if not user:
        raise HTTPException(status_code=400, detail="User profile required")
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if already applied
    existing = db.query(JobApplication).filter(
        JobApplication.user_id == user.id,
        JobApplication.job_id == job_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already applied to this job")
    
    # Create application
    application = JobApplication(
        user_id=user.id,
        job_id=job_id,
        status="applied",
        applied_date=datetime.utcnow(),
        notes=notes
    )
    db.add(application)
    db.commit()
    
    return RedirectResponse(url=f"/job/{job_id}", status_code=303)

@app.get("/applications", response_class=HTMLResponse)
async def job_applications(request: Request, db: Session = Depends(get_db)):
    """User's job applications"""
    user = db.query(UserProfile).first()
    if not user:
        return RedirectResponse(url="/profile")
    
    applications = db.query(JobApplication).filter(
        JobApplication.user_id == user.id
    ).order_by(JobApplication.created_at.desc()).all()
    
    return templates.TemplateResponse("applications.html", {
        "request": request,
        "applications": applications
    })

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, db: Session = Depends(get_db)):
    """Analytics and insights dashboard"""
    user = db.query(UserProfile).first()
    
    # Job market statistics
    total_jobs = db.query(Job).filter(Job.is_active == True).count()
    remote_jobs = db.query(Job).filter(
        Job.is_active == True,
        Job.remote_option == "remote"
    ).count()
    
    # Experience level distribution
    exp_levels = db.query(Job.experience_level, db.func.count(Job.id)).filter(
        Job.is_active == True
    ).group_by(Job.experience_level).all()
    
    # Top companies by job count
    top_companies = db.query(Company.name, db.func.count(Job.id)).join(Job).filter(
        Job.is_active == True
    ).group_by(Company.name).order_by(db.func.count(Job.id).desc()).limit(10).all()
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "stats": {
            "total_jobs": total_jobs,
            "remote_jobs": remote_jobs,
            "remote_percentage": (remote_jobs / total_jobs * 100) if total_jobs > 0 else 0,
            "exp_levels": dict(exp_levels),
            "top_companies": dict(top_companies)
        }
    })

# API Endpoints
@app.get("/api/jobs")
async def api_jobs(
    page: int = 1,
    limit: int = 20,
    location: Optional[str] = None,
    experience_level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """API endpoint for jobs"""
    offset = (page - 1) * limit
    
    query = db.query(Job).filter(Job.is_active == True)
    
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if experience_level:
        query = query.filter(Job.experience_level == experience_level)
    
    jobs = query.order_by(Job.job_score.desc()).offset(offset).limit(limit).all()
    
    return {
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company": job.company.name if job.company else None,
                "location": job.location,
                "experience_level": job.experience_level,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "remote_option": job.remote_option,
                "job_score": job.job_score,
                "apply_url": job.apply_url
            }
            for job in jobs
        ],
        "page": page,
        "limit": limit,
        "total": query.count()
    }

@app.post("/api/refresh-matches")
async def api_refresh_matches(db: Session = Depends(get_db)):
    """API endpoint to refresh job matches"""
    user = db.query(UserProfile).first()
    if not user:
        raise HTTPException(status_code=400, detail="User profile required")
    
    matches = enhanced_matcher.match_user_to_jobs(user.id)
    
    return {
        "message": "Matches refreshed successfully",
        "match_count": len(matches)
    }

if __name__ == "__main__":
    import uvicorn
    web_config = config.web_config
    uvicorn.run(
        app,
        host=web_config.get("host", "0.0.0.0"),
        port=web_config.get("port", 8000),
        debug=web_config.get("debug", False)
    )
