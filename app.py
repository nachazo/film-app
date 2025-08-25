import os
import json
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect, url_for
from urllib.parse import quote_plus
# --- CAMBIO: Importaciones necesarias para la pausa ---
import time
import random

app = Flask(__name__)

# --- CONFIGURACIÓN ---
FILMAFFINITY_LIST_URL = "https://www.filmaffinity.com/es/userlist.php?user_id=629775&list_id=1013"
CACHE_FILE = "cache.json"

def generate_youtube_search_url(movie_title):
    """Genera una URL de búsqueda en YouTube para el tráiler."""
    query = quote_plus(f"{movie_title} trailer castellano")
    return f"https://www.youtube.com/results?search_query={query}"

def scrape_filmaffinity():
    """Realiza el scraping de la lista de FilmAffinity y devuelve los datos."""
    scraper = cloudscraper.create_scraper()
    movies_data = []
    
    print("Obteniendo la lista principal...")
    try:
        response = scraper.get(FILMAFFINITY_LIST_URL)
        response.raise_for_status()
    except Exception as e:
        print(f"Error al acceder a la lista principal: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    movie_items = soup.find_all('li', {'data-movie-id': True})

    if not movie_items:
        print("No se encontraron películas en la lista.")
        return []

    print(f"Se encontraron {len(movie_items)} películas. Obteniendo detalles...")

    for item in movie_items:
        try:
            movie_id = item['data-movie-id']
            card = item.find('div', class_='movie-card')
            
            title_element = card.find('div', class_='mc-title').find('a')
            title = title_element.text.strip()
            
            year_element = card.find('span', class_='mc-year')
            year = year_element.text.strip() if year_element else "N/A"
            
            rating_element = card.find('div', class_='avg')
            rating = rating_element.text.strip() if rating_element else "N/A"

            poster_img = card.find('img')
            poster_url = poster_img.get('data-srcset', '').split(',')[-1].split(' ')[1] if poster_img and poster_img.get('data-srcset') else 'https://via.placeholder.com/150x210'

            details_url = title_element['href']
            
            type_element = item.find('span', class_='type')
            content_type = type_element.text.strip() if type_element else "Película"

            print(f"Obteniendo sinopsis para: {title}")
            details_response = scraper.get(details_url)
            details_soup = BeautifulSoup(details_response.text, 'html.parser')
            
            synopsis_element = details_soup.find('dd', {'itemprop': 'description'})
            synopsis = synopsis_element.text.strip() if synopsis_element else "Sinopsis no disponible."
            
            search_url = generate_youtube_search_url(title)

            movies_data.append({
                "id": movie_id,
                "title": title,
                "year": year,
                "rating": rating,
                "poster": poster_url,
                "synopsis": synopsis,
                "type": content_type,
                "trailer_search_url": search_url
            })

            # --- CAMBIO CLAVE: Añadir una pausa aleatoria ---
            # Esperamos entre 1 y 3 segundos antes de la siguiente petición
            # para no saturar el servidor y evitar el error 429.
            sleep_time = random.uniform(1, 3)
            print(f"Esperando {sleep_time:.2f} segundos...")
            time.sleep(sleep_time)

        except Exception as e:
            print(f"Error procesando una película ('{title if 'title' in locals() else 'Desconocido'}'): {e}")
            continue

    if not movies_data:
        print("El scraping finalizó pero no se pudo extraer ninguna película.")
        return []

    movies_data.reverse()
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
        
    print("Scraping completado y datos cacheados.")
    return movies_data

@app.route('/')
def index():
    """Página principal que muestra las películas desde la caché."""
    movies = []
    if not os.path.exists(CACHE_FILE):
        print("Caché no encontrada. Realizando scraping inicial...")
        movies = scrape_filmaffinity()
    else:
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                movies = json.load(f)
                if not movies:
                    print("La caché estaba vacía. Refrescando datos...")
                    movies = scrape_filmaffinity()
        except (IOError, json.JSONDecodeError):
            print("Error leyendo la caché. Refrescando datos...")
            movies = scrape_filmaffinity()
            
    return render_template('index.html', movies=movies)

@app.route('/refresh')
def refresh():
    """Fuerza el scraping de los datos y actualiza la caché."""
    print("Refrescando datos bajo demanda...")
    scrape_filmaffinity()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)