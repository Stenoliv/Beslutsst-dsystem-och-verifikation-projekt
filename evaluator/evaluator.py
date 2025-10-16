import pandas as pd
import numpy as np

class Evaluator:
    @staticmethod
    def safe_mean(values):
        """Compute the mean safely, returning 0.0 for empty or NaN-only lists."""
        if not values:
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
        """Compute popularity scores and title ↔ gameId mapping."""
        rating_counts = self.ratings_df["gameId"].value_counts()
        num_users = self.ratings_df["userId"].nunique()
        self.popularity_scores = (rating_counts / num_users).to_dict()

        # title ↔ gameId mappings
        games_unique_titles = self.games_df.drop_duplicates(subset="title")
        self.title_to_id = pd.Series(
            games_unique_titles.gameId.values, index=games_unique_titles.title
        ).to_dict()
        self.gameid_to_title = pd.Series(
            games_unique_titles.title.values, index=games_unique_titles.gameId
        ).to_dict()

    def generate_all_recommendations(self, max_users=30000, random_state=42, n=10):
        """Generate recommendations for a sample of users with multiple seed games for diversity."""
        rng = np.random.default_rng(random_state)
        all_recommendations = {}

        unique_users = self.ratings_df["userId"].unique()
        user_sample = rng.choice(unique_users, size=min(max_users, len(unique_users)), replace=False)

        for user_id in user_sample:
            # Pick a seed game from user's liked games
            user_liked_games = self.ratings_df[
                (self.ratings_df["userId"] == user_id) & (self.ratings_df["rating"] >= 2.5)
            ]
            if not user_liked_games.empty:
                seed_game_id = user_liked_games.sample(1, random_state=rng.integers(1e6))["gameId"].iloc[0]
                seed_game = self.games_df.loc[self.games_df["gameId"] == seed_game_id, "title"].iloc[0]
            else:
                # fallback to a random game
                seed_game = self.games_df.sample(1, random_state=rng.integers(1e6))["title"].iloc[0]

            recs = self.recommender.recommend(user_id, seed_game, n)
            all_recommendations[user_id] = recs if recs else []

        return all_recommendations

    def calculate_precision_at_k(self, all_recommendations, k=10):
        """Compute Precision@k safely using titles."""
        liked_df = (
            self.ratings_df[self.ratings_df["rating"] >= 2.5]
            .groupby("userId")["gameId"]
            .apply(set)
            .to_dict()
        )

        # Convert liked gameIds to titles
        liked_titles = {
            uid: {self.gameid_to_title[g] for g in games if g in self.gameid_to_title}
            for uid, games in liked_df.items()
        }

        precision_list = [
            len(set(recs[:k]) & liked_titles.get(uid, set())) / k
            for uid, recs in all_recommendations.items()
            if recs  # skip empty recommendations
        ]
        return self.safe_mean(precision_list)

    def calculate_coverage(self, all_recommendations):
        """Compute fraction of unique games recommended."""
        all_titles = np.unique([title for recs in all_recommendations.values() for title in recs])
        return len(all_titles) / max(1, self.games_df["title"].nunique())

    def calculate_novelty(self, all_recommendations):
        """Compute novelty as mean -log2(popularity)."""
        if self.popularity_scores is None or self.title_to_id is None:
            raise ValueError("Call fit_recommender() first.")

        titles = np.array([title for recs in all_recommendations.values() for title in recs])

        # Map titles → gameId → popularity
        game_ids = np.array([self.title_to_id.get(title, None) for title in titles])
        popularity = np.array([
            self.popularity_scores.get(gid, 0.0) if gid is not None else 0.0
            for gid in game_ids
        ])

        mask = popularity > 0
        if np.any(mask):
            novelty_values = -np.log2(popularity[mask])
            mean_novelty = np.mean(novelty_values)
        else:
            mean_novelty = 0.0

        return mean_novelty
