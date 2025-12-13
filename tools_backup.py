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
    
    # Mapping catégories - certaines peuvent être vides, on essaie des alternatives
    category_map = {
        'concerts': 1, 'spectacles': 12, 'expositions': 13,
        'theatre': 22, 'clubbing': 57, 'cinema': 58,
        'sports': 74, 'musique': 1, 'art': 13,
        'sport': 74, 'films': 58, 'danse': 28,
        'expo': 13, 'musée': 13, 'musee': 13, 'galerie': 13
    }
    
    # Mots-clés spéciaux pour recherche par filtrage manuel
    expo_keywords = ['expo', 'musée', 'musee', 'galerie', 'exhibition', 'art', 'exposition']
    nature_keywords = ['nature', 'parc', 'balade', 'jardin', 'forêt', 'bois', 'plein air', 
                       'randonnée', 'marché', 'fleur', 'plante', 'vélo', 'outdoor']
    
    query_lower = category.lower()
    mainCategory = None
    is_expo_search = any(kw in query_lower for kw in expo_keywords)
    is_nature_search = any(kw in query_lower for kw in nature_keywords)
    
    for key, value in category_map.items():
        if key in query_lower:
            mainCategory = value
            break

    # Si on ne trouve pas de catégorie précise mais que l'user cherche "Gratuit"
    # On ne filtre pas par catégorie pour avoir plus de choix
    is_search_free = 'gratuit' in query_lower or 'free' in query_lower
    
    # Pour les expos et nature, on récupère TOUS les événements et on filtre manuellement
    # car ces catégories retournent souvent vide via l'API
    url = "https://api.brussels:443/api/agenda/0.0.1/events"
    if mainCategory and not is_expo_search and not is_nature_search:
        url = "https://api.brussels:443/api/agenda/0.0.1/events/category"
        
    params = {"page": 1, "size": 100}  # Plus d'événements pour filtrer
    if mainCategory and not is_expo_search and not is_nature_search:
        params["mainCategory"] = mainCategory
    bearer_token = os.getenv("BRUSSELS_API_BEARER_TOKEN")
    if not bearer_token:
        return "Erreur: Token Brussels API manquant"
    
    headers = {"accept": "application/json", "Authorization": f"Bearer {bearer_token}"}

    try:
        print(f"[DEBUG Brussels] URL: {url}, Params: {params}")  # Debug
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"[DEBUG Brussels] Response keys: {list(data.keys()) if data else 'None'}")  # Debug
        
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

        if not events_list: 
            return f"Aucun événement trouvé sur Brussels Agenda pour '{category}'."

        result = []
        count = 0
        for event in events_list:
            if count >= 8: break

            # Filtre Gratuit manuel si demandé
            is_free_api = event.get('is_free', False)
            if is_search_free and not is_free_api:
                continue
            
            # Filtre EXPO/MUSÉE manuel si on cherche des expos
            # On regarde les catégories de l'événement et le nom
            if is_expo_search:
                event_name = event.get('translations', {}).get('fr', {}).get('name', '').lower()
                event_categories = event.get('categories', [])
                
                # Mots-clés qui indiquent une expo/musée/art
                expo_art_keywords = ['expo', 'exhibition', 'musée', 'museum', 'galerie', 'gallery', 
                                     'art', 'peinture', 'sculpture', 'œuvre', 'collection', 'vernissage',
                                     'atelier', 'installation', 'patrimoine', 'visite']
                
                # Vérifier si l'événement correspond
                is_expo_event = any(kw in event_name for kw in expo_art_keywords)
                
                # Vérifier aussi la catégorie 13 (Art) dans les catégories de l'événement
                for cat in event_categories:
                    if isinstance(cat, dict) and cat.get('id') in [13, 14, 15]:  # Art/Culture
                        is_expo_event = True
                        break
                
                if not is_expo_event:
                    continue  # Skip cet événement, ce n'est pas une expo
            
            # Filtre NATURE manuel si on cherche des activités nature/plein air
            if is_nature_search:
                event_name = event.get('translations', {}).get('fr', {}).get('name', '').lower()
                event_desc = event.get('translations', {}).get('fr', {}).get('description', '').lower()
                
                # Mots-clés qui indiquent une activité nature/plein air
                nature_filter_keywords = ['parc', 'jardin', 'forêt', 'bois', 'balade', 'randonnée', 
                                          'nature', 'plein air', 'outdoor', 'vélo', 'marché', 'fleur',
                                          'plante', 'vert', 'promenade', 'cambre', 'soignes', 'woluwe',
                                          'bruxelles environnement', 'green', 'bio', 'écolo']
                
                # Vérifier nom ET description
                is_nature_event = any(kw in event_name or kw in event_desc for kw in nature_filter_keywords)
                
                if not is_nature_event:
                    continue  # Skip cet événement, ce n'est pas nature

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
                
                # --- DESCRIPTION INTELLIGENTE (Multi-sources) ---
                # Essayer plusieurs champs possibles dans l'ordre de préférence
                desc = (fr.get('description', '') or 
                       fr.get('shortdescr', '') or 
                       fr.get('longdescr', '') or
                       fr.get('body', '') or
                       event.get('description', ''))
                
                # Détection du type d'événement pour la catégorie
                event_category = "Art"  # Par défaut
                name_lower = name.lower()
                
                if any(x in name_lower for x in ['film', 'ciné', 'cinema', 'projection']):
                    event_category = "Cinema"
                elif any(x in name_lower for x in ['concert', 'musique', 'live', 'band']):
                    event_category = "Music"
                elif any(x in name_lower for x in ['expo', 'vernissage', 'galerie', 'musée']):
                    event_category = "Art"
                elif any(x in name_lower for x in ['théâtre', 'theater', 'pièce', 'spectacle']):
                    event_category = "Cinema"
                elif any(x in name_lower for x in ['atelier', 'workshop', 'formation', 'design']):
                    event_category = "Art"
                elif any(x in name_lower for x in ['sport', 'match', 'course', 'yoga', 'fitness', 'padel', 'tennis']):
                    event_category = "Sport"
                elif any(x in name_lower for x in ['balade', 'parc', 'nature', 'jardin', 'forêt', 'bois', 'randonnée', 'fleur', 'plante']):
                    event_category = "Nature"
                
                # Nettoyage HTML avancé
                if desc:
                    import re
                    desc = re.sub(r'<[^>]+>', '', desc)  # Enlève tous les tags HTML
                    desc = desc.replace('&nbsp;', ' ').replace('&amp;', '&')
                    desc = ' '.join(desc.split())  # Enlève espaces multiples
                    # Limiter la longueur
                    if len(desc) > 250:
                        desc = desc[:250] + "..."
                
                # Fallback SEULEMENT si on n'a vraiment rien
                if not desc or len(desc.strip()) < 10:
                    if event_category == "Cinema":
                        if any(x in name_lower for x in ['film', 'ciné', 'cinema']):
                            desc = f"Projection de {name}. Une séance à ne pas manquer pour les cinéphiles."
                        else:
                            desc = f"Spectacle au {place_name}. Un moment captivant vous attend."
                    elif event_category == "Music":
                        desc = f"Concert live au {place_name}. Ambiance garantie et musique de qualité."
                    elif event_category == "Sport":
                        desc = f"Événement sportif au {place_name}. Venez vous dépasser et progresser."
                    elif event_category == "Nature":
                        desc = f"Activité nature au {place_name}. Reconnectez-vous avec la nature."
                    elif event_category == "Art":
                        if any(x in name_lower for x in ['atelier', 'workshop']):
                            desc = f"Atelier créatif au {place_name}. Apprenez de nouvelles compétences."
                        else:
                            desc = f"Exposition au {place_name}. Venez découvrir des œuvres uniques."
                    else:
                        desc = f"Événement au {place_name}. Découvrez {name} dans un cadre unique à Bruxelles."
                
                # Adresse pour le lien
                address_line = place_fr.get('address_line1', '') or place_fr.get('address', '')
                address_zip = place_fr.get('address_zip', '') or place_fr.get('zip', '')
                address_city = place_fr.get('address_city', '') or place_fr.get('city', 'Bruxelles')
                full_address = f"{address_line}, {address_zip} {address_city}".strip(', ')
                if not full_address or full_address == 'Bruxelles':
                    full_address = place_name

                result.append(f"<!-- CATEGORY:{event_category} -->\n"
                            f"{count+1}. {name}\n"
                            f"   📅 {date_str}\n"
                            f"   📍 {place_name}\n"
                            f"   💰 {price_str}\n"
                            f"   🔗 {full_address}\n"
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
    for i, event in enumerate(all_events[:12], 1):
        # Déterminer la catégorie basée sur le titre
        event_name_lower = event['name'].lower()
        eventbrite_category = "Art"  # Par défaut
        
        if any(x in event_name_lower for x in ['concert', 'musique', 'live', 'band', 'festival', 'dj', 'orchestre']):
            eventbrite_category = "Music"
        elif any(x in event_name_lower for x in ['sport', 'fitness', 'yoga', 'danse', 'padel', 'course', 'marathon', 'boxing', 'karaté']):
            eventbrite_category = "Sport"
        elif any(x in event_name_lower for x in ['film', 'cinéma', 'ciné', 'projection', 'théâtre', 'spectacle']):
            eventbrite_category = "Cinema"
        elif any(x in event_name_lower for x in ['balade', 'parc', 'fleur', 'plante', 'jardin', 'forêt', 'bois', 'nature', 'pique-nique', 'marché', 'randonnée']):
            eventbrite_category = "Nature"
        else:
            eventbrite_category = "Art"  # Workshops, exhibitions, etc.
        
        # Améliorer la description : utiliser la vraie si disponible
        desc = event['description']
        if len(desc.strip()) < 20:
            # Fallback si description trop courte
            if eventbrite_category == "Music":
                desc = f"{event['name']}, une expérience musicale à découvrir."
            elif eventbrite_category == "Sport":
                desc = f"{event['name']}, pour vous dépasser et progresser."
            elif eventbrite_category == "Cinema":
                desc = f"{event['name']}, un spectacle à ne pas manquer."
            elif eventbrite_category == "Nature":
                desc = f"{event['name']}, pour vous reconnecter avec la nature."
            else:
                desc = f"{event['name']}, une activité culturelle enrichissante."
        
        result.append(f"<!-- CATEGORY:{eventbrite_category} -->\n"
                     f"{i}. {event['name']}\n"
                     f"   📅 {event['date']}\n"
                     f"   📍 {event['venue']}\n"
                     f"   💰 {event['price']}\n"
                     f"   🔗 {event['url']}\n"
                     f"   Description: {desc}\n")
    
    return "\n".join(result) if result else "Aucun événement trouvé sur EventBrite."

def get_ticketmaster_events(classificationName: str = "Music", genre_filter: str = None) -> str:
    """Récupère les événements Ticketmaster avec filtrage par genre et vraies descriptions."""
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
        'size': 50,
        'sort': 'date,asc',
        'classificationName': search_classification
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        result = []
        events = data.get('_embedded', {}).get('events', [])
        
        seen_names = set()
        count = 0
        for event in events:
            if count >= 10: break
            
            name = event.get('name', 'Événement')
            if name in seen_names:
                continue
            seen_names.add(name)
            
            # --- EXTRACTION DU GENRE ---
            sub_genre = ""
            try:
                classifications = event.get('classifications', [{}])
                if classifications:
                    sub_genre = classifications[0].get('genre', {}).get('name', '')
            except: 
                pass
            
            # Si on cherche un genre spécifique et que l'événement ne matche pas, on passe
            if genre_filter and genre_filter.lower() not in sub_genre.lower():
                continue
            
            # --- DATE ---
            try:
                date_str = event['dates']['start']['localDate']
                if 'localTime' in event['dates']['start']:
                    date_str += " " + event['dates']['start']['localTime'][:-3]
            except:
                date_str = "Date à confirmer"

            # --- LIEU ---
            venue_info = "Bruxelles"
            try:
                v = event['_embedded']['venues'][0]
                venue_info = f"{v.get('name', '')} - {v.get('address', {}).get('line1', '')}"
            except: 
                pass

            # --- PRIX ---
            price = "💶 Prix à vérifier"
            if 'priceRanges' in event and event['priceRanges']:
                pr = event['priceRanges'][0]
                min_p = pr.get('min', 0)
                max_p = pr.get('max', 0)
                currency = pr.get('currency', 'EUR')
                if min_p == 0:
                    price = "🆓 Gratuit"
                elif min_p == max_p:
                    price = f"💰 {min_p} {currency}"
                else:
                    price = f"💰 {min_p}-{max_p} {currency}"
            
            url_evt = event.get('url', 'N/A')
            
            # --- DESCRIPTION : Priorité aux vraies descriptions, fallback sur genre ---
            description = ""
            
            # 1. Essayer description de l'événement si disponible
            if 'description' in event and event['description']:
                description = event['description'][:200]
            elif '_embedded' in event and 'images' in event and event['images']:
                # Parfois l'info est dans les images metadata
                pass
            
            # 2. Si vide, utiliser info
            if not description and 'info' in event and event['info']:
                description = event['info'][:200]
            
            # 3. Fallback sur genre + nom
            if not description or len(description.strip()) < 20:
                if sub_genre:
                    description = f"{name}, un événement de type {sub_genre}. Retrouvez tous les détails sur le site officiel."
                else:
                    description = f"Découvrez {name}. Retrouvez tous les détails sur le site officiel."
            
            # --- CATÉGORIE BASÉE SUR LE GENRE ---
            ticket_category = "Music"  # Défaut pour Ticketmaster (Music, Sports, Arts & Theatre)
            if sub_genre:
                sub_genre_lower = sub_genre.lower()
                if any(x in sub_genre_lower for x in ['comedy', 'humour', 'stand-up']):
                    ticket_category = "Cinema"
                elif any(x in sub_genre_lower for x in ['arts', 'theatre', 'dance', 'ballet']):
                    ticket_category = "Art"
                elif any(x in sub_genre_lower for x in ['sports', 'football', 'boxing', 'wrestling']):
                    ticket_category = "Sport"
                else:
                    ticket_category = "Music"  # Par défaut pour Concert, Musique, etc.

            result.append(f"<!-- CATEGORY:{ticket_category} -->\n"
                          f"{count+1}. {name}\n"
                          f"   📅 {date_str}\n"
                          f"   📍 {venue_info}\n"
                          f"   💰 {price}\n"
                          f"   🔗 {url_evt}\n"
                          f"   Description: {description}\n")
            count += 1
        
        return "\n".join(result) if result else f"Aucun événement trouvé pour {classificationName}."
    except Exception as e:
        return f"Erreur Ticketmaster: {str(e)}"