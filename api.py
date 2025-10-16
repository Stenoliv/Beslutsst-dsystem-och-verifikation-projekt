from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from recommender.hybrid_recommender import HybridRecommender
from recommender.prepare_data import prepare_steam_data_optimized
from evaluator.evaluator import Evaluator
from functools import wraps
import os
import asyncio
import logging

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
    app.state.training_status.update({"status": "initializing", "progress": 0})

    try:
        # Load model if exists and no retraining requested
        if os.path.exists(MODEL_PATH) and not (refit_content or refit_nmf):
            app.state.training_status.update({"status": "loading model", "progress": 50})
            app.state.recommender = HybridRecommender.load(MODEL_PATH)
            app.state.training_status.update({"status": "loaded", "progress": 100})
            return 
        
        # Ensure data prepared
        if not os.path.exists(GAMES_OUT) and not os.path.exists(RATINGS_OUT):
            # Run data-prep in a background thread and wait for the result
            app.state.GAMES_PATH, app.state.RATINGS_PATH = prepare_steam_data_optimized(
                games_out=GAMES_OUT, ratings_out=RATINGS_OUT
            );
        else:
            app.state.GAMES_PATH, app.state.RATINGS_PATH = GAMES_OUT, RATINGS_OUT
        
        # Create recommender
        app.state.recommender = HybridRecommender(app.state.GAMES_PATH, app.state.RATINGS_PATH)

        # Content-based fitting
        if refit_content or not os.path.exists(MODEL_PATH):
            app.state.training_status.update({"status": "fitting content-based", "progress": 20})
            app.state.recommender.fit(refit_content=True, refit_nmf=False)

        # Collaborative (NMF) fitting
        if refit_nmf or not os.path.exists(MODEL_PATH):
            app.state.training_status.update({"status": "fitting collaborative (NMF)", "progress": 50})
            app.state.recommender.fit(refit_content=False, refit_nmf=True)

        # Save model
        app.state.training_status.update({"status": "saving model", "progress": 90})
        app.state.recommender.save(MODEL_PATH)
        app.state.training_status.update({"status": "loaded", "progress": 100})

    except Exception as e:
        app.state.training_status.update({"status": f"error: {e}", "progress": 0})
        logging.error(f"Failed to initialize model: {e}")

# ------------------- Startup & Shutdown ------------------- #
@app.on_event("startup")
async def startup_event():
    app.state.training_status = {"status": "not started", "progress": 0}
    app.state.evaluation_status = {"status": "not started", "progress": 0, "results": None}
    app.state.recommender = None
    
    # Load or train model in background
    asyncio.create_task(asyncio.to_thread(initialize_model))
    logging.info("🚀 FastAPI started and initializing model...")

@app.on_event("shutdown")
def shutdown_event_handler():
    logging.info("🛑 Shutting down FastAPI...")

# ------------------- Evaluation Task ------------------- #
def run_evaluation(max_users: int = 30000, k: int = 10):
    logging.info(f"Starting evaluation with {max_users} users and k = {k}")
    
    app.state.evaluation_status.update({"status": "running", "progress": 0, "results": None})
    try:
        evaluator = Evaluator(app.state.recommender)
        evaluator.fit_recommender()
        app.state.evaluation_status["progress"] = 10
        all_recs = evaluator.generate_all_recommendations(max_users=max_users)
        app.state.evaluation_status["progress"] = 30
        precision_at_k = evaluator.calculate_precision_at_k(all_recs, k=k)
        coverage = evaluator.calculate_coverage(all_recs)
        novelty = evaluator.calculate_novelty(all_recs)

        app.state.evaluation_status.update({
            "status": "completed",
            "progress": 100,
            "results": {
                "num_users_evaluated": len(all_recs),
                "precision_at_k": round(precision_at_k, 4),
                "coverage": round(coverage, 4),
                "novelty": round(novelty, 4),
                "k": k
            }
        })
    except Exception as e:
        app.state.evaluation_status.update({"status": f"error: {e}", "progress": 0, "results": None})
        logging.error(f"Failed to run evaluation: {e}")

# ------------------- API Endpoints ------------------- #
@app.get("/status")
async def get_status():
    return app.state.training_status

@app.get("/evaluate/status")
async def get_eval_status():
    return app.state.evaluation_status

@app.post("/evaluate")
@require_model_loaded
async def evaluate_model(background_tasks: BackgroundTasks, max_users: int = 30000, k: int = 10):
    background_tasks.add_task(run_evaluation, max_users, k)
    return {"status": True, "message": "Evaluation started. Check /evaluate/status for progress."}

@app.get("/recommend")
@require_model_loaded
async def get_recommendations(user_id: int = 0, seed_title: str = "", n: int = 10):
    recs = app.state.recommender.recommend(user_id, seed_title, n)
    return {"user_id": user_id, "seed_title": seed_title, "recommendations": recs}

@app.post("/train")
async def train_model(background_tasks: BackgroundTasks, refit_content: bool = True, refit_nmf: bool = True):
    background_tasks.add_task(initialize_model, refit_content, refit_nmf)
    return {"message": "Training started."}

@app.get("/games/search")
@require_model_loaded
async def search_games(q: str = Query(None, description="Search query for game title"), limit: int = Query(10, ge=1, le=10)):
    """
    Return up to `limit` game titles that contain the query `q`.
    """
    matches = app.state.recommender.games_df["title"].str.contains(q, case=False, na=False)
    titles = app.state.recommender.games_df.loc[matches, "title"].head(limit).tolist()
    return {"games": titles}
