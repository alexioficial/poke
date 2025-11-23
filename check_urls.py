from db import url_col
from collections import Counter


def check_url_stats():
    """Muestra estadísticas sobre las URLs almacenadas"""

    # Contar total de URLs
    total_urls = url_col.count_documents({})
    print(f"📊 Total URLs en la base de datos: {total_urls}")
    print()

    # Obtener todas las URLs para análisis
    all_urls = list(url_col.find({}, {"url": 1, "_id": 0}))

    # Analizar por categoría (basado en el path de la URL)
    categories = Counter()
    for doc in all_urls:
        url = doc["url"]
        # Extraer la categoría del path (ej: /pokemon/, /ability/, etc.)
        if "pokeapi.co/api/v2/" in url:
            path_parts = url.split("pokeapi.co/api/v2/")[1].split("/")
            if path_parts[0]:  # Si hay algo después de v2/
                categories[path_parts[0]] += 1

    # Mostrar las 20 categorías con más URLs
    print("🏆 Top 20 categorías con más URLs:")
    for category, count in categories.most_common(20):
        print(f"  {category}: {count} URLs")

    print()
    print(f"💾 Total de categorías diferentes: {len(categories)}")

    # Algunos ejemplos de URLs
    print("\n📝 Primeras 10 URLs (ejemplo):")
    for i, doc in enumerate(all_urls[:10]):
        print(f"  {i + 1}. {doc['url']}")

    return total_urls


if __name__ == "__main__":
    total = check_url_stats()
    print(f"\n✅ Verificación completada. Total: {total} URLs almacenadas.")
