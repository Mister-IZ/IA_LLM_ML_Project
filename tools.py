import os
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# ========== BRUSSELS API AMÉLIORÉE (Basée sur ton ancien code qui marchait) ==========
class BrusselsAPIFinal:
    """API Brussels avec recherche par keyword, pagination et formatage correct"""
    
    def __init__(self):
        self.consumer_key = os.getenv("BRUSSELS_API_CONSUMER_KEY")
        self.consumer_secret = os.getenv("BRUSSELS_API_CONSUMER_SECRET")
        self.base_url = "https://api.brussels:443/api/agenda/0.0.1"
        self.access_token = self._get_new_token()
    
    def _get_new_token(self) -> Optional[str]:
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
        except Exception as e:
            print(f"[DEBUG Brussels] Erreur token: {e}")
        return None
    
    def get_events(self, keyword: Optional[str] = None, page: int = 1, limit: int = 10) -> List[Dict]:
        """Récupère les événements avec recherche par keyword et pagination"""
        if not self.access_token:
            self.access_token = self._get_new_token()
            if not self.access_token:
                return []
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        # CRUCIAL: Utiliser /events/search pour les keywords (comme ton ancien code)
        if keyword:
            url = f"{self.base_url}/events/search"
            params = {"keyword": keyword, "page": page}
        else:
            url = f"{self.base_url}/events"
            params = {"page": page}
        
        print(f"[DEBUG Brussels] URL: {url}, Params: {params}")
        
        try:
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
                        elif isinstance(results, list):
                            events = results
                
                print(f"[DEBUG Brussels] {len(events)} événements trouvés")
                return events[:limit]
            else:
                print(f"[DEBUG Brussels] Erreur HTTP: {response.status_code}")
        except Exception as e:
            print(f"[DEBUG Brussels] Erreur: {e}")
        
        return []
    
    def load_all_events(self, max_pages: int = 20) -> List[Dict]:
        """Charge plusieurs pages d'événements pour filtrage local"""
        all_events = []
        for page in range(1, max_pages + 1):
            events = self.get_events(None, page=page, limit=50)
            if events:
                all_events.extend(events)
            else:
                break
        print(f"[DEBUG Brussels] Total chargé: {len(all_events)} événements")
        return all_events
    
    def format_event(self, event: Dict) -> Dict:
        """Formatage CORRECT des événements avec dates complètes"""
        translations = event.get("translations", {})
        
        # Titre - chercher dans toutes les langues
        title = None
        for lang in ["fr", "nl", "en", "de"]:
            if lang in translations and isinstance(translations[lang], dict):
                t = translations[lang].get("title") or translations[lang].get("name")
                if t and t.strip():
                    title = t.strip()
                    break
        
        # Si pas de titre trouvé, utiliser le nom de l'événement racine
        if not title:
            title = event.get("name") or event.get("title") or "Événement"
        
        # Description - chercher shortdescr puis description
        description = ""
        full_description = ""
        for lang in ["fr", "nl", "en", "de"]:
            if lang in translations and isinstance(translations[lang], dict):
                desc = (translations[lang].get("shortdescr") or 
                       translations[lang].get("description") or "")
                if desc:
                    full_description = desc
                    # Version courte pour l'affichage
                    description = desc[:150] + "..." if len(desc) > 150 else desc
                    break
        
        # DATE - Formatage correct
        dates = event.get("dates", [])
        start_date = "Date à confirmer"
        
        # Essayer plusieurs sources de date
        if dates and isinstance(dates, list) and len(dates) > 0:
            first_date = dates[0]
            if isinstance(first_date, dict):
                start_date = first_date.get("start", start_date)
        
        # Fallback sur date_start
        if start_date == "Date à confirmer":
            start_date = event.get("date_start", start_date)
        
        # Formatage de la date si trouvée
        if start_date and start_date != "Date à confirmer":
            date_str = str(start_date)
            if "T" in date_str:
                try:
                    date_part, time_part = date_str.split("T")
                    time_part = time_part.split(".")[0].replace("Z", "")[:5]
                    year, month, day = date_part.split("-")
                    # Afficher la date COMPLÈTE avec le jour
                    start_date = f"{day}/{month}/{year} à {time_part}"
                except:
                    start_date = date_str.replace("T", " ").split(".")[0]
            else:
                # Si c'est juste une heure sans date, ajouter "Aujourd'hui"
                if ":" in date_str and len(date_str) <= 8:
                    start_date = f"Aujourd'hui à {date_str[:5]}"
        
        # Lieu
        place = event.get("place", {})
        place_name = "Bruxelles"
        if isinstance(place, dict):
            # Chercher le nom dans les translations du lieu
            place_trans = place.get("translations", {})
            for lang in ["fr", "nl", "en"]:
                if lang in place_trans and isinstance(place_trans[lang], dict):
                    pn = place_trans[lang].get("name")
                    if pn:
                        place_name = pn
                        break
            if place_name == "Bruxelles":
                place_name = place.get("name", "Bruxelles")
        
        # Prix
        is_free = event.get("is_free", False)
        
        # URL
        url = ""
        if "translations" in event:
            for lang in ["fr", "nl", "en"]:
                if lang in translations and isinstance(translations[lang], dict):
                    u = translations[lang].get("url") or translations[lang].get("link")
                    if u:
                        url = u
                        break
        if not url:
            url = event.get("url", "")
        
        return {
            "title": title,
            "description": description,
            "full_description": full_description,
            "start_date": start_date,
            "location": place_name,
            "is_free": is_free,
            "price": "🆓 Gratuit" if is_free else "💶 Payant",
            "url": url
        }


# ========== FILTRAGE INTELLIGENT (Comme ton ancien code) ==========
class EventFilter:
    """Filtre les événements par catégorie avec détection intelligente"""
    
    FILTER_MAP = {
        'film': {
            'keywords': ['film', 'cinéma', 'movie', 'projection', 'cinema', 'films', 'séance'],
            'emoji': '🎬',
            'ml_category': 'Cinema'
        },
        'musique': {
            'keywords': ['musique', 'concert', 'festival', 'groupe', 'dj', 'chanson', 'rock', 'jazz', 'live', 'musical', 'électro', 'rap', 'hip-hop'],
            'emoji': '🎵',
            'ml_category': 'Music'
        },
        'art': {
            'keywords': ['art', 'exposition', 'musée', 'galerie', 'peinture', 'sculpture', 'dessin', 'artistique', 'artiste', 'expo', 'vernissage'],
            'emoji': '🎨',
            'ml_category': 'Art'
        },
        'sport': {
            'keywords': ['sport', 'yoga', 'danse', 'fitness', 'randonnée', 'course', 'vélo', 'athlétisme', 'gym', 'match', 'foot', 'basket', 'padel', 'tennis'],
            'emoji': '⚽',
            'ml_category': 'Sport'
        },
        'theatre': {
            'keywords': ['théâtre', 'spectacle', 'pièce', 'comédie', 'drame', 'improvisation', 'scène', 'theater'],
            'emoji': '🎭',
            'ml_category': 'Cinema'  # Théâtre compte comme Cinema/Culture
        },
        'cuisine': {
            'keywords': ['cuisine', 'food', 'culinaire', 'atelier cuisine', 'chocolat', 'gastronomie', 'cooking', 'recette', 'bière', 'vin'],
            'emoji': '🍳',
            'ml_category': 'Art'  # Cuisine = Art culinaire
        },
        'nature': {
            'keywords': ['nature', 'parc', 'jardin', 'forêt', 'balade', 'randonnée', 'plein air', 'outdoor', 'vélo', 'marché', 'fleur', 'plante', 'bois'],
            'emoji': '🌳',
            'ml_category': 'Nature'
        },
        'gratuit': {
            'keywords': ['gratuit', 'free', 'pas cher', 'gratuite'],
            'emoji': '🆓',
            'ml_category': 'General'
        }
    }
    
    @classmethod
    def detect_filter_type(cls, message: str) -> Tuple[Optional[str], str, str]:
        """
        Détecte le type de filtre à partir du message
        Retourne: (filter_type, emoji, ml_category)
        """
        message_lower = message.lower()
        
        for filter_type, data in cls.FILTER_MAP.items():
            if any(keyword in message_lower for keyword in data['keywords']):
                return filter_type, data['emoji'], data['ml_category']
        
        # Cas spéciaux
        if any(word in message_lower for word in ['ennui', 'seul', 'solitude', 'social', 'rencontrer']):
            return 'social', '😊', 'General'
        
        return None, '🎯', 'General'
    
    @classmethod
    def filter_events(cls, events: List[Dict], filter_type: Optional[str], api: BrusselsAPIFinal) -> List[Dict]:
        """Filtre les événements localement par type"""
        if not filter_type or filter_type == 'social':
            return events[:30]
        
        filtered = []
        filter_data = cls.FILTER_MAP.get(filter_type, {})
        keywords = filter_data.get('keywords', [])
        
        for event in events:
            formatted = api.format_event(event)
            title = formatted['title'].lower()
            description = formatted['description'].lower()
            location = formatted['location'].lower()
            
            # Cas spécial: gratuit
            if filter_type == 'gratuit':
                if formatted['is_free']:
                    filtered.append(event)
                continue
            
            # Filtrage par mots-clés
            if any(term in title or term in description or term in location for term in keywords):
                filtered.append(event)
        
        print(f"[DEBUG Filter] Type '{filter_type}': {len(filtered)} résultats")
        return filtered


# ========== FONCTIONS LEGACY (pour compatibilité avec agent.py actuel) ==========
# Ces fonctions seront appelées par l'agent

# Instance globale de l'API
_brussels_api = None

def get_brussels_api() -> BrusselsAPIFinal:
    """Singleton pour l'API Brussels"""
    global _brussels_api
    if _brussels_api is None:
        _brussels_api = BrusselsAPIFinal()
    return _brussels_api


def get_brussels_events_formatted(query: str, page: int = 1, limit: int = 8) -> Tuple[str, str, List[Dict]]:
    """
    Nouvelle fonction de recherche Brussels avec formatage propre
    Retourne: (texte_formaté, ml_category, liste_événements_bruts)
    """
    api = get_brussels_api()
    
    # Détecter le type de filtre
    filter_type, emoji, ml_category = EventFilter.detect_filter_type(query)
    
    # Stratégie de recherche
    events = []
    
    # 1. Essayer recherche par keyword d'abord
    if filter_type and filter_type != 'gratuit':
        keywords = EventFilter.FILTER_MAP.get(filter_type, {}).get('keywords', [])
        if keywords:
            # Utiliser le premier keyword comme terme de recherche
            events = api.get_events(keyword=keywords[0], page=page, limit=50)
    
    # 2. Si pas assez de résultats, charger tous les événements et filtrer
    if len(events) < 5:
        all_events = api.load_all_events(max_pages=10)
        events = EventFilter.filter_events(all_events, filter_type, api)
    
    if not events:
        return f"❌ Aucune activité trouvée pour '{query}'.", ml_category, []
    
    # Pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_events = events[start_idx:end_idx]
    
    if not page_events:
        return "📭 Plus d'activités disponibles.", ml_category, []
    
    # Formatage
    result = f"{emoji} **ACTIVITÉS À BRUXELLES :**\n\n"
    
    formatted_events = []
    for i, event in enumerate(page_events, 1):
        formatted = api.format_event(event)
        formatted_events.append(formatted)
        
        result += f"{i}. **{formatted['title']}**\n"
        result += f"📅 {formatted['start_date']}\n"
        result += f"📍 {formatted['location']}\n"
        result += f"💰 {formatted['price']}\n"
        if formatted['url']:
            result += f"🔗 {formatted['url']}\n"
        result += f"Description: {formatted['description']}\n"
        result += f"<!-- CATEGORY:{ml_category} -->\n\n"
    
    total_pages = (len(events) // limit) + 1
    result += f"\n💬 **{len(page_events)} activités affichées** (Page {page}/{total_pages})\n"
    result += '<div class="pagination-hint">🔄 Tu veux que je t' + "'" + 'en propose d' + "'" + 'autres ? <button class="suggestion-btn pagination-btn" onclick="handlePagination()">👉 Appuie ici</button></div>'
    
    # DEBUG: Montrer le format exact
    print(f"\n[DEBUG TOOLS] ===== FORMAT GÉNÉRÉ =====")
    print(f"Total length: {len(result)}")
    print(f"Newlines: {result.count(chr(10))}")
    print(f"First 300 chars: {repr(result[:300])}")
    
    return result, ml_category, formatted_events


def get_brussels_events_formatted_with_all(query: str, limit: int = 8) -> Tuple[str, str, List[Dict], List[Dict]]:
    """
    Version qui retourne AUSSI tous les événements filtrés pour pagination locale
    Retourne: (texte_formaté, ml_category, page_events, ALL_filtered_events)
    """
    api = get_brussels_api()
    
    # Détecter le type de filtre
    filter_type, emoji, ml_category = EventFilter.detect_filter_type(query)
    
    # Stratégie de recherche
    events = []
    
    # 1. Essayer recherche par keyword d'abord
    if filter_type and filter_type != 'gratuit':
        keywords = EventFilter.FILTER_MAP.get(filter_type, {}).get('keywords', [])
        if keywords:
            events = api.get_events(keyword=keywords[0], page=1, limit=100)  # Charger plus
    
    # 2. Si pas assez de résultats, charger tous les événements et filtrer
    if len(events) < 5:
        all_events = api.load_all_events(max_pages=10)
        events = EventFilter.filter_events(all_events, filter_type, api)
    
    if not events:
        return f"❌ Aucune activité trouvée pour '{query}'.", ml_category, [], []
    
    # Formater TOUS les événements
    all_formatted = []
    for event in events:
        formatted = api.format_event(event)
        all_formatted.append(formatted)
    
    # Première page
    page_events = all_formatted[:limit]
    
    if not page_events:
        return "📭 Plus d'activités disponibles.", ml_category, [], []
    
    # Formatage de la première page
    result = f"{emoji} **ACTIVITÉS À BRUXELLES :**\n\n"
    
    for i, formatted in enumerate(page_events, 1):
        result += f"{i}. **{formatted['title']}**\n"
        result += f"📅 {formatted['start_date']}\n"
        result += f"📍 {formatted['location']}\n"
        result += f"💰 {formatted['price']}\n"
        if formatted['url']:
            result += f"🔗 {formatted['url']}\n"
        result += f"Description: {formatted['description']}\n"
        result += f"<!-- CATEGORY:{ml_category} -->\n\n"
    
    total_pages = (len(all_formatted) // limit) + 1
    result += f"\n💬 **{len(page_events)} activités affichées** (Page 1/{total_pages})\n"
    result += '<div class="pagination-hint">🔄 Tu veux que je t' + "'" + 'en propose d' + "'" + 'autres ? <button class="suggestion-btn pagination-btn" onclick="handlePagination()">👉 Appuie ici</button></div>'
    
    # DEBUG: Montrer le format exact
    print(f"\n[DEBUG TOOLS WITH_ALL] ===== FORMAT GÉNÉRÉ =====")
    print(f"Total length: {len(result)}")
    print(f"Newlines: {result.count(chr(10))}")
    print(f"First 300 chars: {repr(result[:300])}")
    print(f"Retourne {len(page_events)} events page 1, {len(all_formatted)} total pour pagination")
    
    return result, ml_category, page_events, all_formatted


def get_brussels_events(category: str) -> str:
    """Fonction legacy pour compatibilité - retourne juste le texte"""
    result, _, _ = get_brussels_events_formatted(category)
    return result


# ========== TICKETMASTER API (Gardée simple) ==========
def get_ticketmaster_events(category: str = "Music", genre_filter: str = None) -> str:
    """Récupère les événements via Ticketmaster API"""
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if not api_key:
        return "Erreur: Clé API Ticketmaster manquante"
    
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": api_key,
        "countryCode": "BE",
        "size": 10,
        "sort": "date,asc"
    }
    
    # Mapping catégories
    category_ids = {
        "Music": "KZFzniwnSyZfZ7v7nJ",
        "Sports": "KZFzniwnSyZfZ7v7nE",
        "Arts & Theatre": "KZFzniwnSyZfZ7v7na",
        "Film": "KZFzniwnSyZfZ7v7nn"
    }
    
    if category in category_ids:
        params["classificationId"] = category_ids[category]
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "_embedded" not in data or "events" not in data["_embedded"]:
            return f"Aucun événement Ticketmaster trouvé pour {category}."
        
        events = data["_embedded"]["events"]
        result = []
        
        # Déterminer la catégorie ML
        ml_category = "Music"
        if category == "Sports":
            ml_category = "Sport"
        elif category in ["Arts & Theatre", "Film"]:
            ml_category = "Cinema"
        
        for i, event in enumerate(events[:8], 1):
            name = event.get("name", "Événement")
            
            # Date
            dates = event.get("dates", {}).get("start", {})
            date_str = dates.get("localDate", "Date inconnue")
            time_str = dates.get("localTime", "")
            if time_str:
                date_str = f"{date_str} à {time_str[:5]}"
            
            # Lieu
            venue = event.get("_embedded", {}).get("venues", [{}])[0]
            venue_name = venue.get("name", "Belgique")
            city = venue.get("city", {}).get("name", "")
            location = f"{venue_name}, {city}" if city else venue_name
            
            # Prix
            price_ranges = event.get("priceRanges", [])
            if price_ranges:
                min_p = price_ranges[0].get("min", "?")
                max_p = price_ranges[0].get("max", "?")
                price = f"💶 {min_p} - {max_p} EUR"
            else:
                price = "💶 Prix non communiqué"
            
            # URL
            url = event.get("url", "")
            
            # Description
            desc = event.get("info", "") or event.get("pleaseNote", "") or f"Concert de {name}"
            if len(desc) > 150:
                desc = desc[:150] + "..."
            
            result.append(f"{i}. **{name}**")
            result.append(f"📅 {date_str}")
            result.append(f"📍 {location}")
            result.append(f"💰 {price}")
            if url:
                result.append(f"🔗 {url}")
            result.append(f"Description: {desc}")
            result.append(f"<!-- CATEGORY:{ml_category} -->")
            result.append("")
        
        return "\n".join(result) if result else f"Aucun événement trouvé pour {category}."
        
    except Exception as e:
        return f"Erreur Ticketmaster: {e}"


# ========== EVENTBRITE API (Gardée simple) ==========
def get_eventbrite_events() -> str:
    """Récupère les événements via EventBrite API"""
    api_key = os.getenv("EVENTBRITE_API_KEY")
    if not api_key:
        return "Erreur: Clé API EventBrite manquante"
    
    url = "https://www.eventbriteapi.com/v3/events/search/"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "location.address": "Brussels, Belgium",
        "location.within": "25km",
        "expand": "venue",
        "page_size": 10
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        events = data.get("events", [])
        if not events:
            return "Aucun événement EventBrite trouvé."
        
        result = []
        for i, event in enumerate(events[:6], 1):
            name = event.get("name", {}).get("text", "Événement")
            
            # Date
            start = event.get("start", {})
            date_str = start.get("local", "Date inconnue")
            if "T" in date_str:
                date_str = date_str.replace("T", " à ")[:16]
            
            # Lieu
            venue = event.get("venue", {})
            location = venue.get("name", "Bruxelles")
            
            # Prix
            is_free = event.get("is_free", False)
            price = "🆓 Gratuit" if is_free else "💶 Payant"
            
            # Description
            desc = event.get("description", {}).get("text", "")
            if len(desc) > 150:
                desc = desc[:150] + "..."
            
            # URL
            url = event.get("url", "")
            
            result.append(f"{i}. **{name}**")
            result.append(f"📅 {date_str}")
            result.append(f"📍 {location}")
            result.append(f"💰 {price}")
            if url:
                result.append(f"🔗 {url}")
            result.append(f"Description: {desc}")
            result.append("<!-- CATEGORY:Art -->")
            result.append("")
        
        return "\n".join(result) if result else "Aucun événement trouvé."
        
    except Exception as e:
        return f"Erreur EventBrite: {e}"
