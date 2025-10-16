import pandas as pd
import numpy as np

def prepare_steam_data_optimized(
    games_csv="data/games.csv",
    metadata_json="data/games_metadata.json",
    recs_csv="data/recommendations.csv",
    games_out="data/games_prepared.csv.gz",
    ratings_out="data/ratings_prepared.csv.gz"
):
    print("Preparing Steam data...")

    # -----------------------------
    # 1️⃣ Load games and metadata
    # -----------------------------
    games = pd.read_csv(games_csv, encoding="utf-8")
    
    # Faster JSON loading
    meta_df = pd.read_json(metadata_json, lines=True)

    # Merge on app_id
    games_merged = games.merge(meta_df, on="app_id", how="left")

    # -----------------------------
    # 2️⃣ Create combined 'genres' column
    # -----------------------------
    # Convert tags list to string
    games_merged["tags_str"] = games_merged["tags"].apply(lambda x: " ".join(x) if isinstance(x, list) else "")
    # Combine with description
    games_merged["genres"] = (games_merged["tags_str"] + " " + games_merged["description"].fillna("")).str.strip()

    # Prepare final games dataframe
    games_prepared = games_merged.rename(columns={"app_id": "gameId", "title": "title"})[["gameId", "title", "genres"]]

    # Memory optimization
    games_prepared = games_prepared.astype({"gameId": "int32"})

    # Save prepared games
    games_prepared.to_csv(games_out, index=False, compression='gzip')
    print(f"Saved prepared games data → {games_out}")

    # -----------------------------
    # 3️⃣ Load recommendations
    # -----------------------------
    recs = pd.read_csv(recs_csv, encoding="utf-8")

    # Fill missing hours
    recs["hours"] = recs["hours"].fillna(0)

    # -----------------------------
    # 4️⃣ Compute implicit rating (vectorized)
    # -----------------------------
    base = np.where(recs["is_recommended"]==True, 2.5, 1.5)
    hours_boost = np.log1p(recs["hours"]) / np.log(101)  # log1p(hours)/log(101)
    recs["rating"] = np.minimum(5, base + 2 * hours_boost)

    # -----------------------------
    # 5️⃣ Prepare ratings dataframe
    # -----------------------------
    ratings_prepared = recs.rename(columns={"user_id": "userId", "app_id": "gameId"})[["userId", "gameId", "rating"]]
    ratings_prepared = ratings_prepared.astype({"userId": "int32", "gameId": "int32", "rating": "float32"})

    # Save prepared ratings
    ratings_prepared.to_csv(ratings_out, index=False, compression='gzip')
    print(f"Saved prepared ratings data → {ratings_out}\n")

    return games_out, ratings_out
