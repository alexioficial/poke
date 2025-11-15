from flask import Flask, render_template, request, jsonify
from db import setup_db, pokemon_col

app = Flask(__name__)

PAGE_SIZE = 24

TYPE_CLASSES = {
    "normal": "bg-stone-100 text-stone-700 border-stone-200",
    "fire": "bg-orange-100 text-orange-700 border-orange-200",
    "water": "bg-blue-100 text-blue-700 border-blue-200",
    "grass": "bg-green-100 text-green-700 border-green-200",
    "ice": "bg-cyan-100 text-cyan-700 border-cyan-200",
    "electric": "bg-yellow-100 text-yellow-700 border-yellow-200",
    "psychic": "bg-pink-100 text-pink-700 border-pink-200",
    "fighting": "bg-red-100 text-red-700 border-red-200",
    "poison": "bg-purple-100 text-purple-700 border-purple-200",
    "ground": "bg-amber-100 text-amber-700 border-amber-200",
    "flying": "bg-indigo-100 text-indigo-700 border-indigo-200",
    "bug": "bg-lime-100 text-lime-700 border-lime-200",
    "rock": "bg-yellow-100 text-yellow-800 border-yellow-200",
    "ghost": "bg-violet-100 text-violet-700 border-violet-200",
    "steel": "bg-slate-100 text-slate-700 border-slate-200",
    "dragon": "bg-purple-100 text-purple-800 border-purple-200",
    "dark": "bg-neutral-100 text-neutral-700 border-neutral-200",
    "fairy": "bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200",
}


def pick_sprite(pokemon: dict) -> str:
    sprites = pokemon.get("sprites", {}) or {}
    # Prefer official-artwork, then home, then default
    try:
        return (
            sprites.get("other", {}).get("official-artwork", {}).get("front_default")
            or sprites.get("other", {}).get("home", {}).get("front_default")
            or sprites.get("front_default")
        )
    except Exception:
        return sprites.get("front_default")


def extract_types(pokemon: dict) -> list[str]:
    types = pokemon.get("types", [])
    return [t.get("type", {}).get("name", "?") for t in types]


@app.route("/")
def index():
    # Params
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1
    q = (request.args.get("q") or "").strip()
    id_param = (request.args.get("id") or "").strip()
    types_param = (request.args.get("types") or "").strip()
    sort = (request.args.get("sort") or "id").strip()
    direction = (request.args.get("dir") or "asc").strip().lower()
    height_min = (request.args.get("hmin") or "").strip()
    height_max = (request.args.get("hmax") or "").strip()
    weight_min = (request.args.get("wmin") or "").strip()
    weight_max = (request.args.get("wmax") or "").strip()
    exp_min = (request.args.get("expmin") or "").strip()
    exp_max = (request.args.get("expmax") or "").strip()
    gender_filter = (request.args.get("gender") or "").strip()
    try:
        cols = int(request.args.get("cols", 6))
    except ValueError:
        cols = 6
    if cols not in (3, 4, 5, 6):
        cols = 6
    dir_val = 1 if direction != "desc" else -1

    # Mongo query
    query = {}
    def parse_int(value):
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    if id_param.isdigit():
        query["id"] = int(id_param)
    if types_param:
        type_list = [t.strip().lower() for t in types_param.split(",") if t.strip()]
        if type_list:
            query["types.type.name"] = {"$in": type_list}

    hmin_val = parse_int(height_min)
    hmax_val = parse_int(height_max)
    if hmin_val is not None or hmax_val is not None:
        height_query = {}
        if hmin_val is not None:
            height_query["$gte"] = hmin_val
        if hmax_val is not None:
            height_query["$lte"] = hmax_val
        query["height"] = height_query

    wmin_val = parse_int(weight_min)
    wmax_val = parse_int(weight_max)
    if wmin_val is not None or wmax_val is not None:
        weight_query = {}
        if wmin_val is not None:
            weight_query["$gte"] = wmin_val
        if wmax_val is not None:
            weight_query["$lte"] = wmax_val
        query["weight"] = weight_query

    expmin_val = parse_int(exp_min)
    expmax_val = parse_int(exp_max)
    if expmin_val is not None or expmax_val is not None:
        exp_query = {}
        if expmin_val is not None:
            exp_query["$gte"] = expmin_val
        if expmax_val is not None:
            exp_query["$lte"] = expmax_val
        query["base_experience"] = exp_query

    if gender_filter == "diff":
        query["sprites.front_female"] = {"$ne": None}
    elif gender_filter == "no_diff":
        query["sprites.front_female"] = None

    # Pagination calc
    offset = (page - 1) * PAGE_SIZE
    count = int(pokemon_col.count_documents(query))
    total_pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)

    # Sorting and fetching
    stat_prefix = "stat:"
    pokemons = []
    if sort.startswith(stat_prefix):
        stat_name = sort[len(stat_prefix):]
        pipeline = [
            {"$match": query},
            {"$addFields": {
                "sort_stat": {
                    "$let": {
                        "vars": {
                            "matched": {"$filter": {"input": "$stats", "as": "s", "cond": {"$eq": ["$$s.stat.name", stat_name]}}}
                        },
                        "in": {"$ifNull": [{"$arrayElemAt": ["$$matched.base_stat", 0]}, -1]}
                    }
                }
            }},
            {"$sort": {"sort_stat": dir_val, "id": 1}},
            {"$skip": offset},
            {"$limit": PAGE_SIZE},
            {"$project": {"_id": 0, "id": 1, "name": 1, "types": 1, "sprites": 1}}
        ]
        for doc in pokemon_col.aggregate(pipeline):
            pokemons.append({
                "id": doc.get("id"),
                "name": doc.get("name"),
                "types": extract_types(doc),
                "sprite": pick_sprite(doc),
            })
    else:
        sort_field = "id"
        if sort == "name":
            sort_field = "name"
        elif sort == "type":
            sort_field = "types.0.type.name"
        cursor = (
            pokemon_col
            .find(query, {"id": 1, "name": 1, "types": 1, "sprites": 1, "_id": 0})
            .sort(sort_field, dir_val)
            .skip(offset)
            .limit(PAGE_SIZE)
        )
        for doc in cursor:
            pokemons.append({
                "id": doc.get("id"),
                "name": doc.get("name"),
                "types": extract_types(doc),
                "sprite": pick_sprite(doc),
            })

    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "index.html",
        pokemons=pokemons,
        page=page,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
        type_classes=TYPE_CLASSES,
        q=q,
        id_param=id_param,
        types_param=types_param,
        sort=sort,
        dir=direction,
        height_min=height_min,
        height_max=height_max,
        weight_min=weight_min,
        weight_max=weight_max,
        exp_min=exp_min,
        exp_max=exp_max,
        gender_filter=gender_filter,
        cols=cols,
    )


@app.route("/favorites")
def favorites_page():
    return render_template("favorites.html", type_classes=TYPE_CLASSES)


@app.route("/api/pokemon")
def api_pokemon_by_ids():
    ids_param = request.args.get("ids", "").strip()
    if not ids_param:
        return jsonify([])
    try:
        ids = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
    except Exception:
        ids = []
    if not ids:
        return jsonify([])

    docs = (
        pokemon_col
        .find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "types": 1, "sprites": 1})
        .sort("id", 1)
    )
    result = []
    for d in docs:
        result.append({
            "id": d.get("id"),
            "name": d.get("name"),
            "types": [t.get("type", {}).get("name") for t in (d.get("types") or [])],
            "sprite": pick_sprite(d),
        })
    # Mantener el orden de ids solicitado
    order = {v: i for i, v in enumerate(ids)}
    result.sort(key=lambda x: order.get(x.get("id"), 1_000_000))
    return jsonify(result)


setup_db()


if __name__ == "__main__":
    app.run(debug=True)
