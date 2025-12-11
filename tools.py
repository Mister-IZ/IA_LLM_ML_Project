import os
import requests
from typing import List, Dict, Any
from datetime import datetime

class BrusselsAPI:
    def __init__(self):
        self.consumer_key = os.getenv("BRUSSELS_API_CONSUMER_KEY")
        self.consumer_secret = os.getenv("BRUSSELS_API_CONSUMER_SECRET")
        self.base_url = "https://api.brussels:443/api/agenda/0.0.1"
        self.access_token = self.get_new_token()
    
    def get_new_token(self):
        token_url = "https://api.brussels:443/api/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.consumer_key,
            "client_secret": self.consumer_secret
        }
        try:
            response = requests.post(token_url, data=payload)
            if response.status_code == 200:
                return response.json()["access_token"]
        except:
            return None
        return None

def get_brussels_events(category: str) -> str:
    """Récupère les événements via l'API Brussels."""
    
    category_map = {
        'concerts': 1, 'spectacles': 12, 'expositions': 13,
        'theatre': 14, 'clubbing': 57, 'cinema': 58,
        'sports': 74, 'musique': 1, 'art': 13,
        'sport': 74, 'films': 58, 'danse': 12
    }
    
    query_lower = category.lower()
    mainCategory = None
    for key, value in category_map.items():
        if key in query_lower:
            mainCategory = value
            break

    # Si on ne trouve pas de catégorie précise mais que l'user cherche "Gratuit"
    # On ne filtre pas par catégorie pour avoir plus de choix
    is_search_free = 'gratuit' in query_lower or 'free' in query_lower
    
    url = "https://api.brussels:443/api/agenda/0.0.1/events"
    if mainCategory:
        url = "https://api.brussels:443/api/agenda/0.0.1/events/category"
        params = {"mainCategory": mainCategory, "page": 1}

    bearer_token = os.getenv("BRUSSELS_API_BEARER_TOKEN")
    if not bearer_token:
        return "Erreur: Token Brussels API manquant"
    
    headers = {"accept": "application/json", "Authorization": f"Bearer {bearer_token}"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        # Sécurisation si la réponse est vide ou mal formatée
        data = response.json()
        # if "response" not in data or "results" not in data["response"] or "event" not in data["response"]["results"]:
        #     return f"Aucun événement trouvé pour {category}."

        # all_events = data["response"]["results"]["event"]
        
        # result = []
        # for i, event in enumerate(all_events[:10], 1):
        # Sécurisation du chemin JSON
        events_list = []
        try:
            if "response" in data and "results" in data["response"]:
                 # Parfois c'est une liste directe, parfois c'est sous "event"
                 if "event" in data["response"]["results"]:
                     events_list = data["response"]["results"]["event"]
                 elif isinstance(data["response"]["results"], list):
                     events_list = data["response"]["results"]
        except: pass

        if not events_list: return f"Aucun événement trouvé sur Brussels Agenda."

        result = []
        count = 0
        for event in events_list:
            if count >= 8: break

            # Filtre Gratuit manuel si demandé (l'API le gère mal parfois)
            is_free_api = event.get('is_free', False)
            if is_search_free and not is_free_api:
                continue

            if 'fr' in event.get('translations', {}):
                fr = event['translations']['fr']
                name = fr.get('name', 'Événement')
                
                place_info = event.get('place', {})
                place_fr = place_info.get('translations', {}).get('fr', {}) if isinstance(place_info, dict) else {}
                place_name = "Bruxelles"
                if isinstance(place_info, dict):
                    place_name = place_info.get('translations', {}).get('fr', {}).get('name', 'Bruxelles')

                # Date
                date_str = event.get('date_start', 'Date inconnue')
                try: date_str = date_str.split('T')[0]
                except: pass

                # Prix
                price_str = "🆓 Gratuit" if is_free_api else "💶 Payant"
                
                # --- DESCRIPTION INTELLIGENTE ---
                desc = fr.get('description')
                if not desc:
                    # Fallback si pas de description
                    desc = f"Retrouvez {name} à {place_name}. Une activité idéale pour découvrir la culture locale."
                # Nettoyage HTML basique
                desc = desc.replace('<p>', '').replace('</p>', '').replace('<br>', '')

                result.append(f"{count+1}. {name}\n"
                            f"   📅 {date_str}\n"
                            f"   📍 {place_name}\n"
                            f"   💰 {price_str}\n"
                            f"   🔗 {place_fr.get('address_line1', '')}, {place_fr.get('address_zip', '')} {place_fr.get('address_city', '')}\n"
                            f"   Description: {desc}\n")
                count += 1
        
        if is_search_free and not result:
            return "Désolé, je n'ai pas trouvé d'événements 100% gratuits dans cette catégorie pour l'instant."
            
        return "\n".join(result) if result else "Aucun événement pertinent trouvé."
    
    except Exception as e:
        return f"Erreur API Brussels: {str(e)}"

    #         if 'fr' in event.get('translations', {}):
    #             fr = event['translations']['fr']
    #             place_info = event.get('place', {})
    #             place_fr = place_info.get('translations', {}).get('fr', {}) if isinstance(place_info, dict) else {}
                
    #             # Gestion propre des dates
    #             date_str = event.get('date_start', 'Date inconnue')
    #             try:
    #                 if 'T' in date_str:
    #                     date_str = date_str.split('T')[0]
    #             except: pass

    #             is_free = event.get('is_free', False)
    #             price_str = "🆓 Gratuit" if is_free else "💶 Payant"

    #             result.append(f"{i}. {fr.get('name', 'Événement')}\n"
    #                         f"   📅 {date_str}\n"
    #                         f"   📍 {place_fr.get('name', 'Bruxelles')} - {place_fr.get('address_line1', '')}\n"
    #                         f"   💰 {price_str}\n"
    #                         # f"   🔗 https://agenda.brussels\n" # URL générique car l'API donne rarement l'URL directe
    #                         f"   🔗 {place_fr.get('address_line1', '')}, {place_fr.get('address_zip', '')} {place_fr.get('address_city', '')}\n"
    #                         f"   Description: {fr.get('shortdescr') or 'Pas de description'}\n")
        
    #     return "\n".join(result) if result else f"Aucun événement {category} trouvé."
    
    # except Exception as e:
    #     return f"Erreur API Brussels: {str(e)}"

def get_eventbrite_events() -> str:
    """Récupère les événements EventBrite avec Lieux et Prix."""
    API_TOKEN = os.getenv("EVENTBRITE_PRIVATE_TOKEN")
    if not API_TOKEN:
        return "Erreur: Token EventBrite manquant"
    
    # IDs des lieux (Botanique, Halles St Géry, etc.)
    IdList = ['295288568', '271238193', '278600043', '279838893', '290674563'] 
    
    all_events = []
    
    for venue_id in IdList:
        url = f'https://www.eventbriteapi.com/v3/venues/{venue_id}/events/'
        headers = {'Authorization': f'Bearer {API_TOKEN}'}
        # AJOUT DE 'expand=venue' pour avoir l'adresse !
        params = {'status': 'live', 'order_by': 'start_asc', 'expand': 'venue'} 
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                for event in events:
                    # Gestion du prix
                    is_free = event.get('is_free', False)
                    price_display = "🆓 Gratuit" if is_free else "💶 Payant/Sur réservation"
                    
                    # Gestion du lieu
                    venue_name = "Bruxelles"
                    address = ""
                    if 'venue' in event and event['venue']:
                        venue_name = event['venue'].get('name', 'Lieu inconnu')
                        address = event['venue'].get('address', {}).get('localized_address_display', '')

                    # Gestion de la date
                    date_str = event['start']['local'].replace('T', ' ')[:-3]

                    all_events.append({
                        'name': event['name']['text'],
                        'date': date_str,
                        'venue': f"{venue_name} - {address}",
                        'price': price_display,
                        'url': event['url'],
                        'description': (event.get('description', {}).get('text') or 'Voir lien')[0:150] + "..."
                    })
        except:
            continue
    
    # Formatage texte pour le LLM
    result = []
    for i, event in enumerate(all_events[:12], 1): # Limite à 12 pour pas saturer
        result.append(f"{i}. {event['name']}\n"
                     f"   📅 {event['date']}\n"
                     f"   📍 {event['venue']}\n"
                     f"   💰 {event['price']}\n"
                     f"   🔗 {event['url']}\n"
                     f"   Description: {event['description']}\n")
    
    return "\n".join(result) if result else "Aucun événement trouvé sur EventBrite."

def get_ticketmaster_events(classificationName: str = "Music") -> str:
    """Récupère les événements Ticketmaster avec dédoublonnage et descriptions améliorées."""
    TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_CONSUMER_KEY")
    if not TICKETMASTER_API_KEY:
        return "Erreur: Clé API manquante"
    
    # Mapping précis pour éviter que "Spectacle" ne sorte que des concerts
    search_classification = classificationName
    if classificationName.lower() in ['spectacle', 'theatre', 'théâtre', 'humour', 'comedy']:
        search_classification = 'Arts & Theatre'
    elif classificationName.lower() in ['famille', 'family']:
        search_classification = 'Family'
    
    url = 'https://app.ticketmaster.com/discovery/v2/events.json'
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'countryCode': 'BE',
        'city': 'Brussels',
        'size': 30, # On en prend plus pour pouvoir filtrer les doublons
        'sort': 'date,asc',
        'classificationName': search_classification
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        result = []
        events = data.get('_embedded', {}).get('events', [])
        
        # --- FILTRE ANTI-DOUBLONS ---
        seen_names = set()
        
        count = 0
        for event in events:
            if count >= 10: break # On s'arrête à 10 résultats uniques
            
            name = event.get('name', 'Événement')
            # Si on a déjà vu ce nom exact, on passe (évite les 5 dates de Calogero)
            if name in seen_names:
                continue
            seen_names.add(name)
            
            # Date
            try:
                date_str = event['dates']['start']['localDate']
                if 'localTime' in event['dates']['start']:
                    date_str += " " + event['dates']['start']['localTime'][:-3]
            except:
                date_str = "Date à confirmer"

            # Lieu
            venue_info = "Bruxelles"
            try:
                v = event['_embedded']['venues'][0]
                venue_info = f"{v.get('name', '')} - {v.get('address', {}).get('line1', '')}"
            except: pass

            # Prix
            price = "Non communiqué"
            if 'priceRanges' in event and event['priceRanges']:
                pr = event['priceRanges'][0]
                min_p = pr.get('min', 0)
                price = "🆓 Gratuit" if min_p == 0 else f"{min_p} {pr.get('currency', 'EUR')}"
            
            url_evt = event.get('url', 'N/A')
            
            # --- DESCRIPTION GÉNÉRÉE ---
            # Ticketmaster a rarement des descriptions, donc on en génère une pour le ML
            sub_genre = ""
            try:
                sub_genre = event['classifications'][0]['genre']['name']
            except: pass
            
            description = f"Découvrez {name}, un événement incontournable à {venue_info.split('-')[0].strip()}."
            if sub_genre:
                description += f" Genre : {sub_genre}."

            result.append(f"{count+1}. {name}\n"
                          f"   📅 {date_str}\n"
                          f"   📍 {venue_info}\n"
                          f"   💰 {price}\n"
                          f"   🔗 {url_evt}\n"
                          f"   Description: {description}\n")
            count += 1
        
        return "\n".join(result) if result else f"Aucun événement trouvé pour {classificationName}."
    except Exception as e:
        return f"Erreur Ticketmaster: {str(e)}"