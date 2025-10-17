from fastapi import FastAPI, Query, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from functools import wraps
import os
import asyncio
import logging

from recommender.hybrid_recommender import HybridRecommender
from recommender.prepare_data import prepare_steam_data_optimized
from evaluator.evaluator import Evaluator

# --- DB & Models --- #
from db.database import get_db, init_db
from db.models import JobType, JobStatus, Job
from db.job_utils import (
    create_job, 
    update_job,
    update_job_progress,
    mark_job_running,
    mark_job_completed,
    mark_job_failed,
    list_jobs
)

# ----------------- LOGGER CONFIG ----------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ------------------- Paths ------------------- #
MODEL_PATH = "models/recommender.pkl"
GAMES_OUT = "data/games_prepared.csv.gz"
RATINGS_OUT = "data/ratings_prepared.csv.gz"

# ------------------- FastAPI App ------------------- #
app = FastAPI(title="Steam Hybrid Recommender API")

# --- Init DB --- #
init_db()

# ------------------- CORS ------------------- #
origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------- Decorator ------------------- #
def require_model_loaded(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not hasattr(app.state, "recommender") or app.state.recommender is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        return await func(*args, **kwargs)
    return wrapper

# ------------------- Model Initialization ------------------- #
def initialize_model(refit_content=False, refit_nmf=False):
    """
    Load or train the hybrid recommender model.
    """
    try:
        if os.path.exists(MODEL_PATH) and not (refit_content or refit_nmf):
            app.state.recommender = HybridRecommender.load(MODEL_PATH)
            return
        
        if not os.path.exists(GAMES_OUT) or not os.path.exists(RATINGS_OUT):
            app.state.GAMES_PATH, app.state.RATINGS_PATH = prepare_steam_data_optimized(
                games_out=GAMES_OUT, ratings_out=RATINGS_OUT
            )
        else:
            app.state.GAMES_PATH, app.state.RATINGS_PATH = GAMES_OUT, RATINGS_OUT
        
        app.state.recommender = HybridRecommender(app.state.GAMES_PATH, app.state.RATINGS_PATH)

        # Fit models
        app.state.recommender.fit(refit_content=refit_content, refit_nmf=refit_nmf)
        app.state.recommender.save(MODEL_PATH)

    except Exception as e:
        logging.error(f"Failed to initialize model: {e}")
        raise e

# ------------------- Background Job Handlers ------------------- #
def run_training_job(job_id: int):
    db_gen = get_db()
    db = next(db_gen)
    try:
        mark_job_running(db, job_id)
        initialize_model(refit_content=True, refit_nmf=True)
        mark_job_completed(db, job_id, results={"message": "Model trained successfully"})
    except Exception as e:
        mark_job_failed(db, job_id, str(e))
    finally:
        db.close()

def run_evaluation_job(job_id: int, max_users: int, k: int):
    db_gen = get_db()
    db = next(db_gen)
    try:
        mark_job_running(db, job_id)
        evaluator = Evaluator(app.state.recommender)
        evaluator.fit_recommender()        
        update_job(db, job_id, progress=10)
        all_recs = evaluator.generate_all_recommendations(
            job_id,
            max_users=max_users,
            start_progress=10,
            progress_range=50,
            progress_step=int(max_users/100)
        )

        precision_at_k = evaluator.calculate_precision_at_k(all_recs, k=k)
        update_job_progress(db, job_id, 70)
        coverage = evaluator.calculate_coverage(all_recs)
        update_job_progress(db, job_id, 80)
        novelty = evaluator.calculate_novelty(all_recs)
        update_job_progress(db, job_id, 90)
        
        results = {
            "users_evaluated": len(all_recs),
            "precision@k": round(precision_at_k, 4),
            "coverage": round(coverage, 4),
            "novelty": round(novelty, 4),
            "k": k,
        }

        mark_job_completed(db, job_id, results)
    except Exception as e:
        mark_job_failed(db, job_id, str(e))
    finally:
        db.close()

# ------------------- Startup ------------------- #
@app.on_event("startup")
async def startup_event():
    app.state.recommender = None
    
    # Fix any orphaned jobs in the database
    db_gen = get_db()
    db = next(db_gen)
    try:
        orphaned_jobs = db.query(Job).filter(Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])).all()
        for job in orphaned_jobs:
            job.status = JobStatus.FAILED
            job.error_message = "App crashed or restarted while this job was running"
        db.commit()
    finally:
        db.close()
    
    asyncio.create_task(asyncio.to_thread(initialize_model))
    logging.info("🚀 FastAPI started and initializing model...")

@app.on_event("shutdown")
def shutdown_event_handler():
    logging.info("🛑 Shutting down FastAPI...")

# ------------------- API Endpoints ------------------- #
@app.post("/train")
async def train_model(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = create_job(db, JobType.TRAINING)
    background_tasks.add_task(run_training_job, job.id)
    return {"job_id": job.id, "status": "queued"}

@app.post("/evaluate")
@require_model_loaded
async def evaluate_model(background_tasks: BackgroundTasks, max_users: int = 30000, k: int = 10, db: Session = Depends(get_db)):
    job = create_job(db, JobType.EVALUATION, params={"max_users": max_users, "k": k})
    background_tasks.add_task(run_evaluation_job, job.id, max_users, k)
    return {"job_id": job.id, "status": "queued"}

@app.get("/jobs/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(status_code=500, detail="Job not finished")

    db.delete(job)
    db.commit()

    return {"message": f"Job with id {job_id} has been deleted successfully"}

@app.get("/jobs")
def get_jobs(db: Session = Depends(get_db)):
    return list_jobs(db)

@app.get("/status")
def get_model_status(db: Session = Depends(get_db)):
    """
    Returns the current status of the recommender:
    - loading: model is not yet initialized
    - loaded: model ready
    - training: a training job is currently running
    """
    if not hasattr(app.state, "recommender") or app.state.recommender is None:
        return {"status": "loading", "progress": 0}

    # Check if any training job is running
    running_training = (
        db.query(Job)
        .filter(Job.type == JobType.TRAINING, Job.status == "running")
        .first()
    )

    if running_training:
        return {"status": "training", "progress": running_training.progress}

    return {"status": "loaded", "progress": 100}

@app.get("/games/search")
@require_model_loaded
async def search_games(q: str = Query(None, description="Search query for game title"), limit: int = Query(10, ge=1, le=10)):
    matches = app.state.recommender.games_df["title"].str.contains(q, case=False, na=False)
    titles = app.state.recommender.games_df.loc[matches, "title"].head(limit).tolist()
    return {"games": titles}

@app.get("/recommend")
@require_model_loaded
async def get_recommendations(user_id: int = 0, seed_title: str = "", n: int = 10):
    recs = app.state.recommender.recommend(user_id, seed_title, n)
    return {"user_id": user_id, "seed_title": seed_title, "recommendations": recs}
