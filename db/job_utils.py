from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .models import Job, JobStatus

def create_job(db: Session, job_type, params=None):
    job = Job(type=job_type, status=JobStatus.PENDING, params=params or {})
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def update_job_progress(db, job_id, progress):
    job = db.query(Job).get(job_id)
    if job:
        job.progress = min(progress, 100)
        db.commit()

def update_job(db: Session, job_id, **kwargs):
    job = db.query(Job).get(job_id)
    if not job:
        return None
    for key, value in kwargs.items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job

def mark_job_running(db: Session, job_id):
    return update_job(
        db, job_id,
        status=JobStatus.RUNNING,
        started_at=datetime.now(timezone.utc)
    )
    
def mark_job_completed(db: Session, job_id, results=None):
    return update_job(
        db, job_id,
        status=JobStatus.COMPLETED,
        finished_at=datetime.now(timezone.utc),
        progress=100,
        results=results
    )

def mark_job_failed(db: Session, job_id, error_message):
    return update_job(
        db, job_id,
        status=JobStatus.FAILED,
        finished_at=datetime.now(timezone.utc),
        error_message=str(error_message),
        progress=0
    )
    

def list_jobs(db: Session):
    return db.query(Job).order_by(Job.created_at.desc()).all()