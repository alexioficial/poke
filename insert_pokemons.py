from typing import Generator
from io import BytesIO

import requests
from PIL import Image
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

                colors = extract_sprite_colors(session, pokemon_data)
                if colors is not None:
                    primary, secondary = colors
                    pokemon_data["color_primary"] = primary
                    pokemon_data["color_secondary"] = secondary

            yield pokemon_data


def get_total_pokemon_count() -> int:
    try:
        res = requests.get(f"{BASE_URL}/pokemon", params={"limit": 1}, timeout=10)
        res.raise_for_status()
        data = res.json() or {}
        return int(data.get("count", 0))
    except requests.RequestException:
        return 0


def pick_sprite_url(pokemon: dict) -> str | None:
    sprites = pokemon.get("sprites", {}) or {}
    try:
        return (
            sprites.get("other", {}).get("official-artwork", {}).get("front_default")
            or sprites.get("other", {}).get("home", {}).get("front_default")
            or sprites.get("front_default")
        )
    except Exception:
        return sprites.get("front_default")


def extract_sprite_colors(session: requests.Session, pokemon: dict) -> tuple[str, str] | None:
    url = pick_sprite_url(pokemon)
    if not url:
        return None
    try:
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    try:
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception:
        return None

    img = img.resize((64, 64))
    pixels = img.getdata()

    color_counts: dict[tuple[int, int, int], int] = {}
    for r, g, b, a in pixels:
        if a < 50:
            continue
        if r > 240 and g > 240 and b > 240:
            continue
        if r < 15 and g < 15 and b < 15:
            continue
        key = (r // 16 * 16, g // 16 * 16, b // 16 * 16)
        color_counts[key] = color_counts.get(key, 0) + 1

    if not color_counts:
        return None

    sorted_colors = sorted(color_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
    palette = ["#%02x%02x%02x" % rgb for rgb, _ in sorted_colors]

    if len(palette) == 1:
        primary = palette[0]
        secondary = "#999999"
    else:
        primary, secondary = palette[0], palette[1]

    return primary, secondary


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
        print(f"Guardado/actualizado: {pid}")
    print(f"Guardados/actualizados: {inserted} pokémones")


if __name__ == "__main__":
    save_all_pokemons_to_db()
