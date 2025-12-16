import requests
import csv
import io
from .eventCache import event_cache  # Import global cache


def fetch_brussels_to_cache(category: str) -> list:
    """Fetch events from Brussels API and store in global cache."""
    
    category_map = {
        "concert": 1,
        "show": 12,
        "exhibition": 23,
        "theatre": 49,
        "clubbing": 57,
        "cinema": 58,
        "fairs and shows": 70,
        "markets and bric-a-brac stores": 71,
        "conferences and conventions": 72,
        "courses, placements and workshops": 73,
        "sport": 74,
        "various": 84,
        "cartoons": 90,
        "guided tours": 102,
        "festival": 118,
        "schools": 172,
        "meeting": 254
    }
    
    mainCategory = category_map.get(category.lower(), 74)
    
    url = "https://api.brussels:443/api/agenda/0.0.1/events/category"
    params = {"mainCategory": mainCategory, "page": 1}
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer 097590bb-eca0-35c4-923c-a6a677f52728"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        all_events = response.json()["response"]["results"]["event"]
    except Exception as e:
        print(f"[Brussels] API Error: {e}")
        return []
    
    cached_events = []
    
    for event in all_events:
        if 'fr' in event['translations']:
            fr = event['translations']['fr']
            place_fr = event['place']['translations']['fr']
            
            full_event = {
                "name": fr.get('name'),
                "date": event.get('date_start'),
                "date_start": event.get('date_start'),
                "date_end": event.get('date_end'),
                "venue": place_fr.get('name'),
                "address": f"{place_fr.get('address_line1')}, {place_fr.get('address_zip')} {place_fr.get('address_city')}",
                "price": "Gratuit" if event.get('is_free') else "Payant",
                "description": (fr.get('longdescr') or fr.get('shortdescr') or "").replace('\n', ' ')[:300],
                "url": fr.get('agenda_url') or fr.get('website') or place_fr.get('website')
            }
            
            # Add to cache and GET the ID back
            event_id = event_cache.add_event(full_event, 'brussels')
            full_event['_id'] = event_id  # Store ID in the event dict
            cached_events.append(full_event)
    
    print(f"[Brussels] Cached {len(cached_events)} events for category '{category}'")
    return cached_events


def get_brussels_events_for_llm(category: str) -> str:
    """
    🌱 GREEN VERSION: Returns minimal data for LLM.
    """
    events = fetch_brussels_to_cache(category)
    
    if not events:
        return "Aucun événement Brussels disponible."
    
    # Return MINIMAL format for LLM
    lines = []
    for event in events[:15]:
        event_id = event.get('_id', 'N/A')
        name = (event.get('name') or 'Unknown')[:80]
        date = (event.get('date_start') or 'Date inconnue')[:16]
        desc = (event.get('description') or '')[:80]
        lines.append(f"[{event_id}] {name} | {date} | {desc}")
    
    return "--- BRUSSELS API ---\n" + "\n".join(lines)


# Legacy function
def get_brussels_events(category: str) -> str:
    """Legacy function - now redirects to LLM-optimized version."""
    return get_brussels_events_for_llm(category)