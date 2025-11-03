from typing import Generator
import requests
from db import pokemon_col

BASE_URL = "https://pokeapi.co/api/v2"


def fetch_pokemon_list(limit: int) -> Generator[dict, None, None]:
    if limit <= 0:
        return
    with requests.Session() as session:
        try:
            response = session.get(
                f"{BASE_URL}/pokemon",
                params={"offset": 0, "limit": limit},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            return

        data = response.json()
        for pokemon in data.get("results", []):
            url = pokemon.get("url")
            if not url:
                continue
            try:
                pokemon_response = session.get(url, timeout=10)
                pokemon_response.raise_for_status()
            except requests.RequestException:
                continue
            pokemon_data = pokemon_response.json()
            if isinstance(pokemon_data, dict):
                pokemon_data.pop("moves", None)
                pokemon_data.pop("game_indices", None)
                pokemon_data.pop("cries", None)
                pokemon_data.pop("held_items", None)
            yield pokemon_data


def get_total_pokemon_count() -> int:
    try:
        res = requests.get(f"{BASE_URL}/pokemon", params={"limit": 1}, timeout=10)
        res.raise_for_status()
        data = res.json() or {}
        return int(data.get("count", 0))
    except requests.RequestException:
        return 0


def save_all_pokemons_to_db() -> None:
    total = get_total_pokemon_count()
    if total <= 0:
        return
    inserted = 0
    for p in fetch_pokemon_list(total):
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        if not pid:
            continue
        # Upsert por id
        pokemon_col.update_one({"id": pid}, {"$set": p}, upsert=True)
        inserted += 1
    print(f"Guardados/actualizados: {inserted} pokémones")


if __name__ == "__main__":
    save_all_pokemons_to_db()
