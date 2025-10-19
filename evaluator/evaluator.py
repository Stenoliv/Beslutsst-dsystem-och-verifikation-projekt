import pandas as pd
import numpy as np
from db.database import SessionLocal
from db.models import Job
from db.job_utils import update_job_progress

class Evaluator:
    @staticmethod
    def safe_mean(values):
        """Compute mean safely; return 0.0 for empty or NaN-only arrays."""
        if len(values) == 0:
            return 0.0
        return float(np.nanmean(values))

    def __init__(self, recommender):
        self.recommender = recommender
        self.games_df = self.recommender.games_df
        self.ratings_df = self.recommender.ratings_df
        self.popularity_scores = None
        self.title_to_id = None
        self.gameid_to_title = None

    def fit_recommender(self):
        """Precompute popularity and mapping dictionaries."""
        rating_counts = self.ratings_df["gameId"].value_counts()
        num_users = self.ratings_df["userId"].nunique()
        self.popularity_scores = (rating_counts / num_users).to_dict()

        games_unique = self.games_df.drop_duplicates(subset="title")
        self.title_to_id = pd.Series(games_unique.gameId.values, index=games_unique.title).to_dict()
        self.gameid_to_title = pd.Series(games_unique.title.values, index=games_unique.gameId).to_dict()
        self.popularity_series = pd.Series(self.popularity_scores)

        # For Precision@k vectorization
        self.all_game_ids = np.array(list(self.gameid_to_title.keys()))
        self.gameid_to_idx = {gid: idx for idx, gid in enumerate(self.all_game_ids)}

    def generate_all_recommendations(
        self, 
        job_id: int,
        max_users: int = 30000,
        random_state: int = 42,
        n: int = 10,
        start_progress: int = 0,
        progress_range: int = 100,
        progress_step: int = 50
    ):
        """Generate recommendations for a sample of users with multiple seed games."""
        rng = np.random.default_rng(random_state)
        all_recommendations = {}

        unique_users = self.ratings_df["userId"].unique()
        user_sample = rng.choice(unique_users, size=min(max_users, len(unique_users)), replace=False)

        db = SessionLocal()
        try:
            for i, user_id in enumerate(user_sample, start=1):
                # Choose a seed game
                user_games = self.ratings_df[
                    (self.ratings_df["userId"] == user_id) & (self.ratings_df["rating"] >= 2.5)
                ]
                if not user_games.empty:
                    seed_game_id = user_games.sample(1, random_state=rng.integers(1e6))["gameId"].iloc[0]
                    seed_game = self.games_df.loc[self.games_df["gameId"] == seed_game_id, "title"].iloc[0]
                else:
                    seed_game = self.games_df.sample(1, random_state=rng.integers(1e6))["title"].iloc[0]

                recs = self.recommender.recommend(user_id, seed_game, n)
                all_recommendations[user_id] = recs if recs else []

                # Update progress
                if job_id and (i % progress_step == 0 or i == len(user_sample)):
                    progress_percent = start_progress + int((i / len(user_sample)) * progress_range)
                    update_job_progress(db, job_id, progress_percent)
        finally:
            db.close()

        return all_recommendations

    def calculate_precision_at_k(self, all_recommendations, k=10):
        """Fully vectorized Precision@k using boolean arrays."""
        if not all_recommendations:
            return 0.0

        user_ids = np.array(list(all_recommendations.keys()))
        num_users = len(user_ids)
        num_games = len(self.all_game_ids)

        # Build liked boolean matrix (num_users x num_games)
        liked_matrix = np.zeros((num_users, num_games), dtype=bool)
        user_id_to_idx = {uid: idx for idx, uid in enumerate(user_ids)}

        for uid, games in self.ratings_df[self.ratings_df["rating"] >= 2.5].groupby("userId")["gameId"]:
            if uid in user_id_to_idx:
                idx = user_id_to_idx[uid]
                liked_indices = [self.gameid_to_idx[g] for g in games if g in self.gameid_to_idx]
                liked_matrix[idx, liked_indices] = True

        # Build recommendation indices
        rec_matrix = np.zeros((num_users, k), dtype=int)
        for i, uid in enumerate(user_ids):
            recs = all_recommendations[uid][:k]
            rec_matrix[i, :len(recs)] = [self.gameid_to_idx.get(self.title_to_id.get(title, -1), -1) for title in recs]

        # Calculate hits
        hits = []
        for i in range(num_users):
            valid_indices = rec_matrix[i] >= 0
            if valid_indices.any():
                hits.append(liked_matrix[i, rec_matrix[i, valid_indices]].sum())

        return self.safe_mean(np.array(hits) / k)

    def calculate_coverage(self, all_recommendations):
        """Fraction of unique games recommended."""
        if not all_recommendations:
            return 0.0

        all_titles = np.unique([title for recs in all_recommendations.values() for title in recs])
        return len(all_titles) / max(1, self.games_df["title"].nunique())

    def calculate_novelty(self, all_recommendations):
        """Vectorized novelty: mean -log2(popularity)."""
        if self.popularity_scores is None or self.title_to_id is None:
            raise ValueError("Call fit_recommender() first.")

        titles = [title for recs in all_recommendations.values() for title in recs]
        if not titles:
            return 0.0

        # map titles -> gameId -> popularity using vectorized pandas
        game_ids = pd.Series(titles).map(self.title_to_id)
        popularity = game_ids.map(self.popularity_series).fillna(0.0)
        mask = popularity > 0
        if mask.any():
            return float((-np.log2(popularity[mask])).mean())
        return 0.0
