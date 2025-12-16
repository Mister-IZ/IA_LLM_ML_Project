import requests
import json
import csv
import io
import os 
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta
from dotenv import load_dotenv
from .eventCache import event_cache  # Import global cache

load_dotenv(override=True)
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_PRIVATE_TOKEN")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


def get_embedding(text: str) -> np.ndarray:
    """Get embedding vector for text using sentence-transformers."""
    return embedding_model.encode(text)


def fetch_events_to_cache(force_refresh: bool = False, cache_ttl: int = 36000) -> list:
    """Fetch events from EventBrite API and store in global cache."""
    
    # Check if already cached
    existing = event_cache.get_events_by_source('eventbrite')
    if not force_refresh and len(existing) > 0:
        print(f"[EventBrite] Using {len(existing)} cached events")
        return existing
    
    print("[EventBrite] Fetching fresh events from API...")
    
    IdList = ['295288568', '271238193', '278600043', '279838893', '290674563', 
          '294827703', '282508363','295080090', '244133673','277705833', 
          '294348103', '295110583', '275248603', '287778843', '286500573']
    
    all_events = []
    
    for venue_id in IdList:
        url = f'https://www.eventbriteapi.com/v3/venues/{venue_id}/events/'
        headers = {'Authorization': f'Bearer {EVENTBRITE_API_KEY}'}
        params = {'status': 'live', 'order_by': 'start_asc'}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                events = response.json().get('events', [])
                for event in events:
                    event_name = event['name']['text']
                    event_desc = event.get('description', {}).get('text', '')[:500] if event.get('description') else ""
                    
                    full_event = {
                        "name": event_name,
                        "date": event['start']['local'],
                        "url": event['url'],
                        "description": event_desc.replace('\n', ' '),
                        "venue": "EventBrite Venue",
                        "address": "",
                        "price": "Voir le site"
                    }
                    
                    # Add to global cache
                    event_cache.add_event(full_event, 'eventbrite')
                    all_events.append(full_event)
        except Exception as e:
            print(f"[EventBrite] Error fetching venue {venue_id}: {e}")
    
    print(f"[EventBrite] Cached {len(all_events)} events")
    return all_events


def get_eventBrite_events_for_llm(category_filter: str = None, similarity_threshold: float = 0.15) -> str:
    """
    🌱 GREEN VERSION: Returns minimal data for LLM (ID + name + date + short desc).
    Full data is retrieved later via event_cache.find_event_by_name()
    """
    # Ensure cache is populated
    fetch_events_to_cache()
    
    events = event_cache.get_events_by_source('eventbrite')
    
    if not events:
        return "Aucun événement EventBrite disponible."
    
    # Filter by category using embeddings if specified
    if category_filter:
        category_embedding = get_embedding(category_filter).reshape(1, -1)
        filtered = []
        for event in events:
            text = f"{event['name']}. {event.get('description', '')}"
            event_embedding = get_embedding(text).reshape(1, -1)
            similarity = cosine_similarity(category_embedding, event_embedding)[0][0]
            if similarity >= similarity_threshold:
                filtered.append(event)
        events = filtered
    
    # Return MINIMAL format for LLM
    lines = []
    for event in events[:15]:  # Limit to 15
        event_id = event.get('_id', 'N/A')
        name = event['name'][:80]  # Truncate name
        date = event.get('date', 'Date inconnue')[:16]  # Just date part
        desc = (event.get('description', '') or '')[:80]  # Short description
        lines.append(f"[{event_id}] {name} | {date} | {desc}")
    
    return "--- EVENTBRITE ---\n" + "\n".join(lines)


# Keep old function for backward compatibility
def get_eventBrite_events(category_filter: str = None, similarity_threshold: float = 0.15, force_refresh: bool = False) -> str:
    """Legacy function - now redirects to LLM-optimized version."""
    return get_eventBrite_events_for_llm(category_filter, similarity_threshold)