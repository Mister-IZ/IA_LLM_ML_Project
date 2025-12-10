import os
import requests
from typing import List, Dict, Any
from datetime import datetime

class BrusselsAPI:
    def __init__(self):
        self.consumer_key = os.getenv("BRUSSELS_API_CONSUMER_KEY")
        self.consumer_secret = os.getenv("BRUSSELS_API_CONSUMER_SECRET")
        self.bearer_token = os.getenv("BRUSSELS_API_BEARER_TOKEN")
        self.base_url = "https://api.brussels:443/api/agenda/0.0.1"
        
        if not all([self.consumer_key, self.consumer_secret]):
            raise ValueError("Brussels API credentials manquantes dans les variables d'environnement")
        
        self.access_token = self.get_new_token()
    
    def get_new_token(self):
        """Récupère un nouveau token d'accès"""
        token_url = "https://api.brussels:443/api/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.consumer_key,
            "client_secret": self.consumer_secret
        }
        response = requests.post(token_url, data=payload)
        if response.status_code == 200:
            return response.json()["access_token"]
        return None
    
    def get_events(self, keyword=None, page=1, limit=6):
        """Récupère les événements avec pagination"""
        if not self.access_token:
            return []
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        if keyword:
            url = f"{self.base_url}/events/search"
            params = {"keyword": keyword, "page": page}
        else:
            url = f"{self.base_url}/events"
            params = {"page": page}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            events = []
            if "response" in data:
                response_data = data["response"]
                if "results" in response_data:
                    results = response_data["results"]
                    if "event" in results:
                        events = results["event"]
            
            return events[:limit]
        return []
    
    def format_event(self, event):
        """Formatage des événements avec dates complètes"""
        translations = event.get("translations", {})
        
        # Titre
        title = "Activité à Bruxelles"
        for lang in ["fr", "nl", "en", "de"]:
            if lang in translations and isinstance(translations[lang], dict):
                if translations[lang].get("title"):
                    title = translations[lang]["title"]
                    break
        
        # Description
        description = ""
        for lang in ["fr", "nl", "en", "de"]:
            if lang in translations and isinstance(translations[lang], dict):
                desc = translations[lang].get("shortdescr") or translations[lang].get("description")
                if desc:
                    description = desc
                    break
        
        # Date
        dates = event.get("dates", [])
        start_date = "Date à confirmer"
        if dates and isinstance(dates, list) and len(dates) > 0:
            first_date = dates[0]
            if isinstance(first_date, dict):
                start_date = first_date.get("start", start_date)
                
                if start_date and start_date != "Date à confirmer":
                    date_str = str(start_date)
                    if "T" in date_str:
                        try:
                            date_part, time_part = date_str.split("T")
                            time_part = time_part.split(".")[0]
                            time_part = time_part.replace("Z", "")[:5]
                            
                            year, month, day = date_part.split("-")
                            start_date = f"{day}/{month}/{year} {time_part}h"
                        except:
                            start_date = date_str.replace("T", " ").split(".")[0]
        
        # Lieu
        place = event.get("place", {})
        place_name = "Bruxelles"
        if isinstance(place, dict):
            place_name = place.get("name", "Bruxelles")
        
        return {
            "title": title,
            "description": description[:100] + "..." if len(description) > 100 else description,
            "start_date": start_date,
            "location": place_name,
            "is_free": event.get("is_free", False),
            "full_description": description
        }

def get_brussels_events(category: str) -> str:
    """Fetch events from Brussels API in French.
    
    This function retrieves up to 10 events for the specified category 
    and returns them formatted with all details.
    
    Args:
        category (str): Event category: 'concerts', 'spectacles', 'expositions', 'theatre', 'clubbing', 'cinema', 'sports'
    
    Returns:
        str: Formatted list of up to 10 events with name, date, venue, address, price (Free/Paid), and description.
    """
    
    category_map = {
        'concerts': 1,
        'spectacles': 12,
        'expositions': 13,
        'theatre': 14,
        'clubbing': 57,
        'cinema': 58,
        'sports': 74,
        'musique': 1,
        'art': 13,
        'sport': 74,
        'films': 58,
        'danse': 12
    }
    
    # Mapping intelligent des catégories
    query_lower = category.lower()
    mainCategory = 74  # Par défaut: sports
    
    for key, value in category_map.items():
        if key in query_lower:
            mainCategory = value
            break
    
    url = "https://api.brussels:443/api/agenda/0.0.1/events/category"
    params = {"mainCategory": mainCategory, "page": 1}
    
    # Utilisation du bearer token depuis les variables d'environnement
    bearer_token = os.getenv("BRUSSELS_API_BEARER_TOKEN")
    if not bearer_token:
        return "Erreur: Token d'autorisation Brussels API manquant"
    
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {bearer_token}"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        all_events = response.json()["response"]["results"]["event"]
        
        result = []
        for i, event in enumerate(all_events[:10], 1):
            if 'fr' in event['translations']:
                fr = event['translations']['fr']
                place_info = event.get('place', {})
                place_fr = place_info.get('translations', {}).get('fr', {}) if isinstance(place_info, dict) else {}
                
                result.append(f"{i}. {fr.get('name', 'Événement sans nom')}\n"
                            f"   📅 {event.get('date_start', 'N/A')} - {event.get('date_end', 'N/A')}\n"
                            f"   📍 {place_fr.get('name', 'Lieu non spécifié')}\n"
                            f"   Adresse: {place_fr.get('address_line1', '')}, {place_fr.get('address_zip', '')} {place_fr.get('address_city', '')}\n"
                            f"   Prix: {'🆓 Gratuit' if event.get('is_free') else '💶 Payant'}\n"
                            f"   Description: {fr.get('longdescr') or fr.get('shortdescr') or 'N/A'}\n")
        
        return "\n".join(result) if result else f"Aucun événement {category} trouvé via l'API Brussels"
    
    except Exception as e:
        return f"Erreur avec l'API Brussels: {str(e)}"

def get_eventbrite_events() -> str:
    """Get upcoming events from EventBrite in Brussels."""
    API_TOKEN = os.getenv("EVENTBRITE_PRIVATE_TOKEN")
    if not API_TOKEN:
        return "Erreur: Token EventBrite manquant dans les variables d'environnement"
    
    IdList = ['295288568', '271238193', '278600043', '279838893', '290674563', 
              '294827703', '282508363', '295080090', '244133673', '277705833', 
              '294348103', '295110583', '275248603', '287778843', '286500573']
    all_events = []
    
    for venue_id in IdList:
        url = f'https://www.eventbriteapi.com/v3/venues/{venue_id}/events/'
        headers = {
            'Authorization': f'Bearer {API_TOKEN}',
        }
        params = {
            'status': 'live',  
            'order_by': 'start_asc',  
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            for event in events:
                event_info = {
                    'name': event['name']['text'],
                    'date': event['start']['local'],
                    'url': event['url'],
                    'description': event['description']['text'][:200] if event.get('description') else 'No description'
                }
                all_events.append(event_info)
    
    # Format as text
    result = []
    for i, event in enumerate(all_events, 1):
        result.append(f"{i}. {event['name']}\n"
                     f"   📅 {event['date']}\n"
                     f"   📝 {event['description']}\n"
                     f"   🔗 {event['url']}\n")
    
    return "\n".join(result) if result else "No events found"

def get_ticketmaster_events(classificationName: str = "Music") -> str:
    """Fetch events from Ticketmaster API in Belgium."""
    TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_CONSUMER_KEY")
    if not TICKETMASTER_API_KEY:
        return "Erreur: Clé API Ticketmaster manquante dans les variables d'environnement"
    
    url = 'https://app.ticketmaster.com/discovery/v2/events.json'
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'countryCode': 'BE',
        'city': 'Brussels',
        'size': 25,
        'sort': 'date,asc',
        'classificationName': classificationName
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        result = []
        events = data.get('_embedded', {}).get('events', [])
        
        for i, event in enumerate(events, 1):
            name = event['name']
            date_info = event['dates']['start']
            date_str = date_info.get('dateTime', date_info.get('localDate', 'Date not specified'))
            venue = event['_embedded']['venues'][0]['name'] if '_embedded' in event and 'venues' in event['_embedded'] else 'Venue not specified'
            address = event['_embedded']['venues'][0]['address']['line1'] if '_embedded' in event and 'venues' in event['_embedded'] and 'address' in event['_embedded']['venues'][0] else 'Address not specified'
            price = 'N/A'
            if 'priceRanges' in event and event['priceRanges']:
                pr = event['priceRanges'][0]
                price = f"{pr.get('min', '?')} - {pr.get('max', '?')} {pr.get('currency', 'EUR')}"
            
            result.append(f"{i}. {name}\n   📅 {date_str}\n   📍 {venue} - {address}\n   💰 {price}\n   🔗 {event['url']}\n")
        
        return "\n".join(result) if result else "No events found"
    except Exception as e:
        return f"Error fetching Ticketmaster events: {str(e)}"