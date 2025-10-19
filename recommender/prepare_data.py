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

    games = pd.read_csv(games_csv, encoding="utf-8")

    meta_df = pd.read_json(metadata_json, lines=True)

    games_merged = games.merge(meta_df, on="app_id", how="left")

    games_merged["tags_str"] = games_merged["tags"].apply(lambda x: " ".join(x) if isinstance(x, list) else "")
   
    games_merged["genres"] = (games_merged["tags_str"] + " " + games_merged["description"].fillna("")).str.strip()

    games_prepared = games_merged.rename(columns={"app_id": "gameId", "title": "title"})[["gameId", "title", "genres"]]

    games_prepared = games_prepared.astype({"gameId": "int32"})

    games_prepared.to_csv(games_out, index=False, compression='gzip')
    print(f"Saved prepared games data → {games_out}")

    recs = pd.read_csv(recs_csv, encoding="utf-8")

    recs["hours"] = recs["hours"].fillna(0)

    base = np.where(recs["is_recommended"]==True, 2.5, 1.5)
    hours_boost = np.log1p(recs["hours"]) / np.log(101)  
    recs["rating"] = np.minimum(5, base + 2 * hours_boost)


    ratings_prepared = recs.rename(columns={"user_id": "userId", "app_id": "gameId"})[["userId", "gameId", "rating"]]
    ratings_prepared = ratings_prepared.astype({"userId": "int32", "gameId": "int32", "rating": "float32"})

    ratings_prepared.to_csv(ratings_out, index=False, compression='gzip')
    print(f"Saved prepared ratings data → {ratings_out}\n")

    return games_out, ratings_out
