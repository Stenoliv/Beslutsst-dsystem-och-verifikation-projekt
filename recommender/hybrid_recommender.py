import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import joblib
from pathlib import Path
import logging
from sklearnex import patch_sklearn
patch_sklearn(verbose=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("sklearnex").setLevel(logging.WARNING)

class HybridRecommender:
    def __init__(self, game_data_path, rating_data_path):
        logger.info("Initializing HybridRecommender...")
        self.games_df = pd.read_csv(game_data_path)
        self.ratings_df = pd.read_csv(rating_data_path)
        logger.info(f"Loaded {len(self.games_df)} games and {len(self.ratings_df)} ratings.")
        self.content_recommender = self._ContentBasedRecommender(self.games_df)
        self.nmf_model = None
        self.user_item_matrix = None
        self.user_mapper = None
        self.game_mapper = None
        self.game_inv_mapper = None

    def fit(self, refit_content=True, refit_nmf=True, n_components=20):
        if refit_content:
            logger.info("Fitting content-based recommender (TF-IDF)...")
            self.content_recommender.fit()
            logger.info(f"TF-IDF matrix shape: {self.content_recommender.tfidf_matrix.shape}")

        if refit_nmf:
            logger.info("Preparing user-item matrix for NMF collaborative filtering...")
            user_ids = self.ratings_df["userId"].unique()
            game_ids = self.ratings_df["gameId"].unique()
            self.user_mapper = {uid: i for i, uid in enumerate(user_ids)}
            self.game_mapper = {gid: i for i, gid in enumerate(game_ids)}
            self.game_inv_mapper = {i: gid for gid, i in self.game_mapper.items()}

            user_index = self.ratings_df["userId"].map(self.user_mapper)
            game_index = self.ratings_df["gameId"].map(self.game_mapper)
            ratings = self.ratings_df["rating"].astype(np.float32)  # save memory

            self.user_item_matrix = csr_matrix(
                (ratings, (user_index, game_index)),
                shape=(len(user_ids), len(game_ids))
            )
            logger.info(f"User-item matrix shape: {self.user_item_matrix.shape}")

            logger.info(f"Fitting NMF model with {n_components} components...")
            self.nmf_model = NMF(
                n_components=n_components,
                init="random",
                random_state=42,
                max_iter=400,
            )
            self.nmf_model.fit(self.user_item_matrix)
            logger.info("NMF model fitted successfully.")

    def recommend(self, user_id, seed_title, n=10):
        logger.debug(f"Generating recommendations for user {user_id} with seed '{seed_title}'")
        content_recs = self.content_recommender.recommend(seed_title, n)
        collaborative_recs = []

        if self.nmf_model is not None and user_id in self.user_mapper:
            user_idx = self.user_mapper[user_id]
            user_vector = self.user_item_matrix[user_idx]
            user_P = self.nmf_model.transform(user_vector)
            item_Q = self.nmf_model.components_
            scores = user_P @ item_Q
            scores_series = pd.Series(scores.flatten(), index=list(self.game_mapper.keys()))

            rated_games = self.ratings_df[self.ratings_df["userId"] == user_id]["gameId"]
            scores_series = scores_series.drop(index=rated_games, errors="ignore")

            top_game_ids = scores_series.nlargest(n).index.tolist()
            collaborative_recs = self.games_df[self.games_df["gameId"].isin(top_game_ids)]["title"].tolist()

        combined = list(dict.fromkeys(content_recs + collaborative_recs))
        logger.debug(f"Returning {len(combined[:n])} combined recommendations")
        return combined[:n]

    def save(self, path="models/recommender.pkl"):
        Path(path).parent.mkdir(exist_ok=True, parents=True)
        joblib.dump({
            "nmf_model": self.nmf_model,
            "user_mapper": self.user_mapper,
            "game_mapper": self.game_mapper,
            "game_inv_mapper": self.game_inv_mapper,
            "user_item_matrix": self.user_item_matrix,
            "tfidf_matrix": self.content_recommender.tfidf_matrix,
            "game_indices": self.content_recommender.game_indices,
            "games_df": self.games_df,
            "ratings_df": self.ratings_df
        }, path)
        logger.info(f"Recommender saved to {path}")

    @classmethod
    def load(cls, path):
        logger.info(f"Loading recommender from {path}")
        data = joblib.load(path)
        obj = cls.__new__(cls)
        obj.nmf_model = data["nmf_model"]
        obj.user_mapper = data["user_mapper"]
        obj.game_mapper = data["game_mapper"]
        obj.game_inv_mapper = data["game_inv_mapper"]
        obj.user_item_matrix = data["user_item_matrix"]
        obj.games_df = data["games_df"]
        obj.ratings_df = data["ratings_df"]
        obj.content_recommender = cls._ContentBasedRecommender(obj.games_df)
        obj.content_recommender.tfidf_matrix = data["tfidf_matrix"]
        obj.content_recommender.game_indices = data["game_indices"]
        logger.info("Recommender loaded successfully")
        return obj

    class _ContentBasedRecommender:
        def __init__(self, games_df):
            self.games_df = games_df.copy()

        def fit(self):
            self.games_df = self.games_df.reset_index(drop=True)
            self.games_df["genres"] = self.games_df["genres"].fillna("")
            tfidf = TfidfVectorizer(stop_words="english")
            self.tfidf_matrix = tfidf.fit_transform(self.games_df["genres"])
            self.game_indices = pd.Series(self.games_df.index, index=self.games_df["title"]).drop_duplicates()

        def recommend(self, title, n=10):
            if title not in self.game_indices:
                logging.warning(f"Title '{title}' not found in TF-IDF index.")
                return []

            idx = self.game_indices[title]
            sim_scores = cosine_similarity(self.tfidf_matrix[idx], self.tfidf_matrix).flatten()
            sim_scores[idx] = 0  # exclude self

            top_indices = np.argsort(sim_scores)[-n:][::-1]
            top_indices = [i for i in top_indices if i < len(self.games_df)]

            idx_to_title = pd.Series(self.games_df["title"].values, index=np.arange(len(self.games_df)))
            top_titles = idx_to_title[top_indices].tolist()
            return top_titles
