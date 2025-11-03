from pymongo import MongoClient
from dotenv import load_dotenv
from os import getenv

load_dotenv()

client = MongoClient(getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[getenv("MONGO_DB", "poke")]

pokemon_col = db["pokemon"]


def setup_db():
    try:
        pokemon_col.create_index("id", unique=True)
        pokemon_col.create_index("name", unique=True)
    except Exception:
        print("Ya existen los indices")
