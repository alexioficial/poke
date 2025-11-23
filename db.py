from pymongo import MongoClient
from dotenv import load_dotenv
from os import getenv

load_dotenv()

client = MongoClient(getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[getenv("MONGO_DB", "poke")]

pokemon_col = db["pokemon"]
url_col = db["url"]


def setup_db() -> None:
    try:
        pokemon_col.create_index("id", unique=True)
        pokemon_col.create_index("name", unique=True)
        url_col.create_index("url", unique=True)
    except Exception:
        print("Ya existen los indices")


if __name__ == "__main__":
    setup_db()
