import os
import json
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect, url_for
from youtubesearchpython import VideosSearch

app = Flask(__name__)

# --- CONFIGURACIÓN ---
FILMAFFINITY_LIST_URL = "https://www.filmaffinity.com/es/userlist.php?user_id=629775&list_id=1013"
CACHE_FILE = "cache.json"

def get_trailer_url(movie_title, year):
    """Busca en YouTube el tráiler de la película."""
    try:
        query = f"{movie_title} {year} trailer español"
        videos_search = VideosSearch(query, limit=1)
        results = videos_search.result()
        if results['result']:
            return results['result'][0]['link']
    except Exception as e:
        print(f"Error buscando tráiler para '{movie_title}': {e}")
    # URL de fallback por si falla la búsqueda
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 

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

            # --- CORRECCIÓN CLAVE AQUÍ ---
            # El href ya es una URL absoluta, no hay que añadirle el dominio.
            details_url = title_element['href']
            
            print(f"Obteniendo sinopsis para: {title}")
            details_response = scraper.get(details_url)
            details_soup = BeautifulSoup(details_response.text, 'html.parser')
            
            synopsis_element = details_soup.find('dd', {'itemprop': 'description'})
            synopsis = synopsis_element.text.strip() if synopsis_element else "Sinopsis no disponible."
            
            trailer_url = get_trailer_url(title, year)

            movies_data.append({
                "id": movie_id,
                "title": title,
                "year": year,
                "rating": rating,
                "poster": poster_url,
                "synopsis": synopsis,
                "trailer_url": trailer_url
            })
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
    # Si no hay caché, la primera carga la creará.
    if not os.path.exists(CACHE_FILE):
        print("Caché no encontrada. Realizando scraping inicial...")
        movies = scrape_filmaffinity()
    else:
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                movies = json.load(f)
                # Si la caché está vacía por un fallo anterior, re-scrapeamos
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