import requests
import csv
import os
import io
from dotenv import load_dotenv
from .eventCache import event_cache  # Import global cache

load_dotenv(override=True)

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_CONSUMER_KEY")


def fetch_ticketmaster_to_cache(classificationName: str) -> list:
    """Fetch events from Ticketmaster API and store in global cache."""

    classificationList = [ "music", "sports", "arts", "film", "miscellaneous" ]
    
    if not TICKETMASTER_API_KEY:
        print("[TicketMaster] ERROR: Missing API key")
        return []
    
    if classificationName.lower() in classificationList:
        url = 'https://app.ticketmaster.com/discovery/v2/events.json'
        params = {
            'apikey': TICKETMASTER_API_KEY,
            'countryCode': 'BE',
            'size': 25,
            'sort': 'date,asc',
            'city': 'Brussels',
            'classificationName': classificationName
        }
    else:
        url = 'https://app.ticketmaster.com/discovery/v2/events.json'
        params = {
            'apikey': TICKETMASTER_API_KEY,
            'countryCode': 'BE',
            'size': 25,
            'sort': 'date,asc',
            'city': 'Brussels'
        }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[TicketMaster] API Error: {e}")
        return []
    
    events = data.get('_embedded', {}).get('events', [])
    cached_events = []
    
    for event in events:
        venue_data = event.get('_embedded', {}).get('venues', [{}])[0]
        
        price_str = "Prix non disponible"
        if 'priceRanges' in event and event['priceRanges']:
            pr = event['priceRanges'][0]
            price_min = pr.get('min')
            price_max = pr.get('max')
            currency = pr.get('currency', 'EUR')
            if price_min and price_max:
                price_str = f"{price_min}-{price_max} {currency}"
            elif price_min:
                price_str = f"À partir de {price_min} {currency}"
        
        full_event = {
            "name": event['name'],
            "date": event['dates']['start'].get('dateTime', event['dates']['start'].get('localDate')),
            "venue": venue_data.get('name'),
            "address": venue_data.get('address', {}).get('line1'),
            "price": price_str,
            "description": event.get('info', event.get('pleaseNote', ''))[:300],
            "url": event['url']
        }
        
        # Add to cache and GET the ID back
        event_id = event_cache.add_event(full_event, 'ticketmaster')
        full_event['_id'] = event_id  # Store ID in the event dict
        cached_events.append(full_event)
    
    print(f"[TicketMaster] Cached {len(cached_events)} events for '{classificationName}'")
    return cached_events


def get_ticketmaster_events_for_llm(classificationName: str) -> str:
    """
    🌱 GREEN VERSION: Returns minimal data for LLM.
    """
    events = fetch_ticketmaster_to_cache(classificationName)
    
    if not events:
        return "Aucun événement TicketMaster disponible."
    
    # Return MINIMAL format for LLM
    lines = []
    for event in events[:15]:
        event_id = event.get('_id', 'N/A')
        name = event['name'][:80]
        date = (event.get('date') or 'Date inconnue')[:16]
        desc = (event.get('description') or '')[:80]
        lines.append(f"[{event_id}] {name} | {date} | {desc}")
    
    return "--- TICKETMASTER ---\n" + "\n".join(lines)


# Legacy function
def get_ticketmaster_events(classificationName: str) -> str:
    """Legacy function - now redirects to LLM-optimized version."""
    return get_ticketmaster_events_for_llm(classificationName)