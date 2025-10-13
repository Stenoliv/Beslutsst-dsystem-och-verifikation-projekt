import pandas as pd
import numpy as np
import json
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import NMF
from scipy.sparse import csr_matrix

def prepare_steam_data(
    games_csv="data/games.csv",
    metadata_json="data/games_metadata.json",
    recs_csv="data/recommendations.csv",
    games_out="data/games_prepared.csv",
    ratings_out="data/ratings_prepared.csv"
):
    print("Preparing Steam data...")

    # Load games and metadata
    games = pd.read_csv(games_csv, encoding="utf-8")
    with open(metadata_json, encoding="utf-8") as f:
        metadata = [json.loads(line) for line in f]
    meta_df = pd.DataFrame(metadata)

    # Merge and create genres-like column
    games_merged = games.merge(meta_df, on="app_id", how="left")
    games_merged["genres"] = games_merged["tags"].apply(
        lambda tags: " ".join(tags) if isinstance(tags, list) else ""
    ) + " " + games_merged["description"].fillna("")

    # Simplified dataframe for recommender
    games_prepared = games_merged.rename(
        columns={"app_id": "gameId", "title": "title"}
    )[["gameId", "title", "genres"]]

    games_prepared.to_csv(games_out, index=False)
    print(f"Saved prepared games data → {games_out}")

    # Load recommendations (user-game interactions)
    recs = pd.read_csv(recs_csv, encoding="utf-8")

    # Compute implicit rating based on review and playtime
    def compute_rating(row):
        base = 2.5 if row.get("is_recommended", False) else 1.5
        hours = row.get("hours", 0)
        hours_boost = np.log1p(hours) / np.log(100 + 1)
        return float(min(5, base + 2 * hours_boost))

    recs["rating"] = recs.apply(compute_rating, axis=1)

    # Rename columns for compatibility
    ratings_prepared = recs.rename(
        columns={"user_id": "userId", "app_id": "gameId"}
    )[["userId", "gameId", "rating"]]

    ratings_prepared.to_csv(ratings_out, index=False)
    print(f"Saved prepared ratings data → {ratings_out}\n")

    return games_out, ratings_out

class HybridRecommender:
    def __init__(self, game_data_path, rating_data_path):
        self.games_df = pd.read_csv(game_data_path)
        self.ratings_df = pd.read_csv(rating_data_path)
        self.content_recommender = self._ContentBasedRecommender(self.games_df)
        self.nmf_model = None
        self.user_item_matrix = None
        self.user_mapper = None
        self.game_mapper = None
        self.game_inv_mapper = None

    def fit(self):
        self.content_recommender.fit()

        # Map users and games to contiguous indices
        user_ids = self.ratings_df["userId"].unique()
        game_ids = self.ratings_df["gameId"].unique()

        self.user_mapper = {uid: i for i, uid in enumerate(user_ids)}
        self.game_mapper = {gid: i for i, gid in enumerate(game_ids)}
        self.game_inv_mapper = {i: gid for gid, i in self.game_mapper.items()}

        # Convert ratings to sparse matrix
        user_index = self.ratings_df["userId"].map(self.user_mapper)
        game_index = self.ratings_df["gameId"].map(self.game_mapper)
        ratings = self.ratings_df["rating"].astype(float)

        self.user_item_matrix = csr_matrix(
            (ratings, (user_index, game_index)),
            shape=(len(user_ids), len(game_ids))
        )

        # Fit NMF model on sparse matrix
        self.nmf_model = NMF(
            n_components=20,
            init="random",
            random_state=42,
            max_iter=400
        )
        self.nmf_model.fit(self.user_item_matrix)

    def recommend(self, user_id, game_title_seed, num_recommendations=10):
        content_recs = self.content_recommender.recommend(game_title_seed, num_recommendations)

        collaborative_recs = []
        if user_id in self.user_mapper:
            user_idx = self.user_mapper[user_id]
            user_vector = self.user_item_matrix[user_idx].toarray().reshape(1, -1)
            user_P = self.nmf_model.transform(user_vector)
            item_Q = self.nmf_model.components_
            predicted_scores = np.dot(user_P, item_Q).flatten()

            scores_series = pd.Series(predicted_scores, index=list(self.game_mapper.keys()))
            rated_games = self.ratings_df[self.ratings_df["userId"] == user_id]["gameId"]
            scores_series = scores_series.drop(index=rated_games, errors="ignore")

            top_game_ids = scores_series.nlargest(num_recommendations).index.tolist()
            collaborative_recs = self.games_df[self.games_df["gameId"].isin(top_game_ids)]["title"].tolist()

        combined_recs = list(dict.fromkeys(content_recs + collaborative_recs))
        unique_recs = list(dict.fromkeys(combined_recs).keys())
        return unique_recs[:num_recommendations]

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
                return []
            idx = self.game_indices[title]
            sim_scores = cosine_similarity(self.tfidf_matrix[idx], self.tfidf_matrix).flatten()
            sim_scores[idx] = 0  # avoid recommending itself
            sim_indices = np.argsort(sim_scores)[-n:][::-1]
            valid_indices = sim_indices[sim_indices < len(self.games_df)]
            return self.games_df["title"].iloc[valid_indices].tolist()

class Evaluator:
    def __init__(self, game_data_path, rating_data_path):
        self.recommender = HybridRecommender(game_data_path, rating_data_path)
        self.games_df = self.recommender.games_df
        self.ratings_df = self.recommender.ratings_df
        self.popularity_scores = None
        self.title_to_id = None

    def fit_recommender(self):
        print("Fitting recommender model...")
        self.recommender.fit()
        print("Recommender fitted.")

        print("Calculating popularity scores...")
        rating_counts = self.ratings_df["gameId"].value_counts()
        num_users = self.ratings_df["userId"].nunique()
        self.popularity_scores = rating_counts / num_users
        games_unique_titles = self.games_df.drop_duplicates(subset="title")
        self.title_to_id = pd.Series(games_unique_titles.gameId.values, index=games_unique_titles.title)
        print("Popularity scores calculated.\n")

    def generate_all_recommendations(self, max_users=30000):
        print(f"Generating recommendations for up to {max_users} users...")

        all_recommendations = {}

        # Choose a popular game as the seed
        seed_game = self.games_df["title"].value_counts().index[0]

        # Sample a subset of users
        user_sample = np.random.choice(
            self.ratings_df["userId"].unique(),
            size=min(max_users, self.ratings_df["userId"].nunique()),
            replace=False
        )

        for i, user_id in enumerate(user_sample, start=1):
            recs = self.recommender.recommend(user_id, seed_game, 10)
            all_recommendations[user_id] = recs

            if i % 1000 == 0:
                print(f"  Processed {i}/{len(user_sample)} users...")

        print("All sampled recommendations generated.\n")
        return all_recommendations

    def calculate_precision_at_k(self, all_recommendations, k=10):
        precisions = []
        title_to_id = self.games_df.set_index("title")["gameId"].to_dict()
        user_groups = self.ratings_df.groupby("userId")

        for user_id, recs in all_recommendations.items():
            liked_games = set()
            if user_id in user_groups.groups:
                user_ratings = user_groups.get_group(user_id)
                liked_games = set(user_ratings[user_ratings["rating"] >= 2.5]["gameId"].unique())

            hits = sum(1 for title in recs[:k] if title_to_id.get(title) in liked_games)
            precisions.append(hits / k)

        return float(np.mean(precisions)) if precisions else 0.0

    def calculate_coverage(self, all_recommendations):
        recommended_titles = {title for recs in all_recommendations.values() for title in recs}
        num_unique_recommended = len(recommended_titles)
        total_unique_games = int(self.games_df["title"].nunique())
        return float(num_unique_recommended / total_unique_games) if total_unique_games > 0 else 0.0

    def calculate_novelty(self, all_recommendations):
        if self.popularity_scores is None or self.title_to_id is None:
            raise ValueError("Call fit_recommender() first.")
        user_novelties = []
        for recs in all_recommendations.values():
            novs = []
            for title in recs:
                gid = self.title_to_id.get(title)
                if gid not in self.popularity_scores:
                    continue
                pop = self.popularity_scores[gid]
                if pd.isna(pop) or pop <= 0:
                    continue
                novs.append(-math.log2(float(pop)))
            user_novelties.append(np.mean(novs) if novs else 0.0)
        return float(np.mean(user_novelties)) if user_novelties else 0.0

if __name__ == "__main__":
    games_csv, ratings_csv = prepare_steam_data()

    evaluator = Evaluator(game_data_path=games_csv, rating_data_path=ratings_csv)
    evaluator.fit_recommender()

    all_recs = evaluator.generate_all_recommendations()

    precision = evaluator.calculate_precision_at_k(all_recs)
    coverage = evaluator.calculate_coverage(all_recs)
    novelty = evaluator.calculate_novelty(all_recs)

    print("\n--- Evaluation Metrics ---")
    print(f"Average Precision@10: {precision:.4f}")
    print(f"Catalog Coverage: {coverage:.4f}")
    print(f"Average Novelty: {novelty:.4f}\n")

    example_user = np.random.choice(evaluator.ratings_df["userId"].unique())
    seed_game = evaluator.games_df["title"].value_counts().index[0]
    user_recs = evaluator.recommender.recommend(example_user, seed_game, num_recommendations=5)

    print(f"Example Recommendations for User {example_user}:")
    for i, game in enumerate(user_recs, start=1):
        print(f"   {i}. {game}")
