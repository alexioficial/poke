from tools import fetch, is_valid_url
from pymongo.errors import DuplicateKeyError
from db import url_col
from threading import Thread, Lock
from queue import Queue
import time

# Todas las URLs de endpoints de lista que deben usar offset/limit
LIST_ENDPOINT_URLS = [
    "https://pokeapi.co/api/v2/ability/",
    "https://pokeapi.co/api/v2/berry/",
    "https://pokeapi.co/api/v2/berry-firmness/",
    "https://pokeapi.co/api/v2/berry-flavor/",
    "https://pokeapi.co/api/v2/characteristic/",
    "https://pokeapi.co/api/v2/contest-effect/",
    "https://pokeapi.co/api/v2/contest-type/",
    "https://pokeapi.co/api/v2/egg-group/",
    "https://pokeapi.co/api/v2/encounter-condition/",
    "https://pokeapi.co/api/v2/encounter-condition-value/",
    "https://pokeapi.co/api/v2/encounter-method/",
    "https://pokeapi.co/api/v2/evolution-chain/",
    "https://pokeapi.co/api/v2/evolution-trigger/",
    "https://pokeapi.co/api/v2/gender/",
    "https://pokeapi.co/api/v2/generation/",
    "https://pokeapi.co/api/v2/growth-rate/",
    "https://pokeapi.co/api/v2/item/",
    "https://pokeapi.co/api/v2/item-attribute/",
    "https://pokeapi.co/api/v2/item-category/",
    "https://pokeapi.co/api/v2/item-fling-effect/",
    "https://pokeapi.co/api/v2/item-pocket/",
    "https://pokeapi.co/api/v2/language/",
    "https://pokeapi.co/api/v2/location/",
    "https://pokeapi.co/api/v2/location-area/",
    "https://pokeapi.co/api/v2/machine/",
    "https://pokeapi.co/api/v2/move/",
    "https://pokeapi.co/api/v2/move-ailment/",
    "https://pokeapi.co/api/v2/move-battle-style/",
    "https://pokeapi.co/api/v2/move-category/",
    "https://pokeapi.co/api/v2/move-damage-class/",
    "https://pokeapi.co/api/v2/move-learn-method/",
    "https://pokeapi.co/api/v2/move-target/",
    "https://pokeapi.co/api/v2/nature/",
    "https://pokeapi.co/api/v2/pal-park-area/",
    "https://pokeapi.co/api/v2/pokeathlon-stat/",
    "https://pokeapi.co/api/v2/pokedex/",
    "https://pokeapi.co/api/v2/pokemon/",
    "https://pokeapi.co/api/v2/pokemon-color/",
    "https://pokeapi.co/api/v2/pokemon-form/",
    "https://pokeapi.co/api/v2/pokemon-habitat/",
    "https://pokeapi.co/api/v2/pokemon-shape/",
    "https://pokeapi.co/api/v2/pokemon-species/",
    "https://pokeapi.co/api/v2/region/",
    "https://pokeapi.co/api/v2/stat/",
    "https://pokeapi.co/api/v2/super-contest-effect/",
    "https://pokeapi.co/api/v2/type/",
    "https://pokeapi.co/api/v2/version/",
    "https://pokeapi.co/api/v2/version-group/",
]

# Parametros para endpoints de lista
PARAMS = {"offset": 0, "limit": 99999}

# Variables globales para controlar el proceso
url_queue = Queue()
processed_urls = set()
lock = Lock()
active_threads = 0
MAX_THREADS = 10  # Número de hilos concurrentes


def insert_url(url: str) -> bool:
    try:
        url_col.insert_one({"url": url})
        print(f"✓ Inserted: {url}")
        return True
    except DuplicateKeyError:
        # print(f"⚠ Url {url} already exists.")
        return False


def should_use_params(url: str) -> bool:
    """Determina si una URL debe usar parámetros offset/limit"""
    # Normalizar la URL removiendo el trailing slash
    normalized_url = url.rstrip("/")
    for endpoint_url in LIST_ENDPOINT_URLS:
        # Verificar si la URL coincide con alguno de los endpoints de lista
        if normalized_url == endpoint_url.rstrip("/"):
            return True
    return False


def extract_urls_from_data(data, found_urls: set):
    """Extrae todas las URLs de una estructura de datos recursivamente"""
    if isinstance(data, str):
        if is_valid_url(data):
            found_urls.add(data)
    elif isinstance(data, dict):
        for v in data.values():
            extract_urls_from_data(v, found_urls)
    elif isinstance(data, list):
        for i in data:
            extract_urls_from_data(i, found_urls)


def process_url(url: str):
    """Procesa una URL: hace fetch, extrae URLs y las agrega a la cola"""
    global active_threads

    try:
        # Determinar si usar parámetros
        params = PARAMS if should_use_params(url) else {}

        # Hacer fetch
        data = fetch(url, params)

        # Extraer todas las URLs del JSON
        found_urls = set()
        extract_urls_from_data(data, found_urls)

        # Agregar URLs nuevas a la cola
        for new_url in found_urls:
            with lock:
                if new_url not in processed_urls:
                    processed_urls.add(new_url)
                    if insert_url(new_url):
                        url_queue.put(new_url)

    except Exception as e:
        print(f"✗ Error processing {url}: {type(e).__name__}")


def worker():
    """Worker thread que consume URLs de la cola"""
    global active_threads

    while True:
        url = url_queue.get()

        if url is None:  # Señal de terminación
            url_queue.task_done()
            break

        with lock:
            active_threads += 1

        process_url(url)

        with lock:
            active_threads -= 1

        url_queue.task_done()


def iter_through_urls():
    """Función principal que inicia el scraping con hilos"""
    global active_threads

    print(f"🚀 Starting URL scraping from {len(LIST_ENDPOINT_URLS)} list endpoints")
    print(f"📊 Using {MAX_THREADS} concurrent threads")

    # Agregar todas las URLs iniciales de los endpoints
    for start_url in LIST_ENDPOINT_URLS:
        processed_urls.add(start_url)
        insert_url(start_url)
        url_queue.put(start_url)

    # Crear threads
    threads = []
    for _ in range(MAX_THREADS):
        t = Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)

    # Monitorear progreso
    last_count = 0
    while True:
        time.sleep(2)

        with lock:
            queue_size = url_queue.qsize()
            processed_count = len(processed_urls)
            threads_active = active_threads

        if processed_count != last_count:
            print(
                f"📈 Progress: {processed_count} URLs processed | {queue_size} in queue | {threads_active} active threads"
            )
            last_count = processed_count

        # Si la cola está vacía y no hay threads activos, terminamos
        if queue_size == 0 and threads_active == 0:
            break

    # Terminar threads
    for _ in range(MAX_THREADS):
        url_queue.put(None)

    for t in threads:
        t.join()

    print(f"✅ Completed! Total URLs processed: {len(processed_urls)}")


def fetch_and_update_url(url: str, url_id) -> None:
    """Hace fetch a una URL y actualiza el documento con los datos"""
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # segundos base para el delay

    for attempt in range(MAX_RETRIES):
        try:
            # Determinar si usar parámetros offset/limit
            params = PARAMS if should_use_params(url) else {}

            # Hacer fetch
            data = fetch(url, params)

            # Actualizar el documento en la DB
            url_col.update_one({"_id": url_id}, {"$set": {"data": data}})
            print(f"✓ Fetched and saved: {url}")

            # Pequeño delay para no sobrecargar la API
            time.sleep(0.1)
            return  # Éxito, salir de la función

        except Exception as e:
            error_msg = f"{type(e).__name__} - {str(e)}"

            if attempt < MAX_RETRIES - 1:
                # Calcular delay con backoff exponencial
                delay = RETRY_DELAY * (2**attempt)
                print(
                    f"⚠ Error fetching {url} (attempt {attempt + 1}/{MAX_RETRIES}): {error_msg}"
                )
                print(f"  ↻ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                # Último intento falló
                print(f"✗ Failed after {MAX_RETRIES} attempts: {url} - {error_msg}")


def process_url_batch(urls_batch: list) -> None:
    """Procesa un batch de URLs"""
    for url_doc in urls_batch:
        fetch_and_update_url(url_doc["url"], url_doc["_id"])


def put_urls_data() -> None:
    """Itera sobre todas las URLs y hace fetch a cada una, guardando los datos en paralelo"""

    print("🚀 Starting data fetching for all URLs...")

    # Obtener todas las URLs de la colección
    all_urls = list(url_col.find({}, {"_id": 1, "url": 1}))
    total_urls = len(all_urls)

    print(f"📊 Total URLs to fetch: {total_urls}")

    # Dividir en batches de 1000
    BATCH_SIZE = 1000
    batches = [all_urls[i : i + BATCH_SIZE] for i in range(0, total_urls, BATCH_SIZE)]

    print(f"📦 Created {len(batches)} batches of up to {BATCH_SIZE} URLs")
    print(f"🔧 Starting {len(batches)} threads (1 per batch)...\n")

    # Crear un thread por cada batch
    threads = []
    for i, batch in enumerate(batches):
        t = Thread(target=process_url_batch, args=(batch,), name=f"Batch-{i + 1}")
        t.start()
        threads.append(t)
        print(f"  Thread {i + 1}/{len(batches)} started (processing {len(batch)} URLs)")

    # Esperar a que todos los threads terminen
    print("\n⏳ Waiting for all threads to complete...\n")
    for i, t in enumerate(threads):
        t.join()
        print(f"  ✓ Thread {i + 1}/{len(threads)} completed")

    print(f"\n✅ Completed! All {total_urls} URLs have been fetched and saved.")


if __name__ == "__main__":
    # Descomentar la que quieras ejecutar:
    iter_through_urls()  # Para obtener todas las URLs
    put_urls_data()  # Para hacer fetch de los datos
