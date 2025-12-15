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

load_dotenv(override=True)
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_PRIVATE_TOKEN")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


def get_embedding(text: str) -> np.ndarray:
    """Get embedding vector for text using sentence-transformers.
    
    Args:
        text: Text to embed
        
    Returns:
        np.ndarray: Embedding vector
    """
    return embedding_model.encode(text)

# In-memory cache with TTL using a dict
class CacheWithTTL:
    def __init__(self):
        self.cache = {}
        self.expiry = {}
    
    def get(self, key):
        if key in self.cache:
            if datetime.now() < self.expiry.get(key, datetime.now()):
                return self.cache[key]
            else:
                del self.cache[key]
                del self.expiry[key]
        return None
    
    def set(self, key, value, ttl_seconds):
        self.cache[key] = value
        self.expiry[key] = datetime.now() + timedelta(seconds=ttl_seconds)

# Initialize cache
local_cache = CacheWithTTL()

def fetch_events_to_cache(force_refresh: bool = False, cache_ttl: int = 36000) -> list:
    """Fetch events from API and cache locally.
    
    Args:
        force_refresh: If True, bypass cache and fetch fresh data
        cache_ttl: Cache time-to-live in seconds (default: 10 hours)
    
    Returns:
        list: List of event dictionaries
    """
    cache_key = 'eventbrite:events:all'
    
    # Try to get from cache first
    if not force_refresh:
        cached_data = local_cache.get(cache_key)
        if cached_data:
            print("Using cached events from local memory")
            return cached_data
    
    # Fetch fresh data from API
    #print("Fetching fresh events from API")
    # IdList = ['295288568', '271238193', '278600043', '279838893', '290674563', 
    #       '294827703', '282508363','295080090', '244133673','277705833', 
    #       '294348103', '295110583', '275248603', '287778843', '286500573',
    #        '279399083','279399743', '279400403', '295198507','275935733',
    #         '292626743', '283994593', '285424813', '251187193', '295487905',
    #          '294728683', '291984493', '295103082','287935003', '295184668', 
    #          '295258183', '286548243','295173004', '295311294', '295284070']

    IdList = ['295288568', '271238193', '278600043', '279838893', '290674563', 
          '294827703', '282508363','295080090', '244133673','277705833', 
          '294348103', '295110583', '275248603', '287778843', '286500573']
    
    all_events = []
    
    for venue_id in IdList:
        url = f'https://www.eventbriteapi.com/v3/venues/{venue_id}/events/'
        headers = {'Authorization': f'Bearer {EVENTBRITE_API_KEY}'}
        params = {'status': 'live', 'order_by': 'start_asc'}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            events = response.json().get('events', [])
            for event in events:
                event_name = event['name']['text']
                event_desc = event.get('description', {}).get('text', '')[:500] if event.get('description') else ""
                
                all_events.append({
                    "name": event_name,
                    "date": event['start']['local'],
                    "url": event['url'],
                    "description": event_desc.replace('\n', ' '),
                    "full_text": f"{event_name}. {event_desc}"
                })
    
    # Cache locally
    local_cache.set(cache_key, all_events, cache_ttl)
    print(f"Cached {len(all_events)} events in local memory")
    
    return all_events



def get_eventBrite_events(category_filter: str = None, similarity_threshold: float = 0.15, force_refresh: bool = False) -> str:
    """Get upcoming events from EventBrite as CSV, optionally filtered by category."""
    
    # Get events from local cache (or fetch if not cached)
    all_events = fetch_events_to_cache(force_refresh)
    
    filtered_events = []
    
    # Get category embedding if filter is specified
    category_embedding = None
    if category_filter:
        category_embedding = get_embedding(category_filter).reshape(1, -1)
    
    for event in all_events:
        # If category filter is set, check similarity
        include_event = True
        similarity_score = None
        
        if category_filter and category_embedding is not None:
            event_embedding = get_embedding(event['full_text']).reshape(1, -1)
            similarity_score = cosine_similarity(category_embedding, event_embedding)[0][0]
            include_event = similarity_score >= similarity_threshold
        
        if include_event:
            filtered_events.append({
                "name": event['name'],
                "date": event['date'],
                "url": event['url'],
                "description": event['description'],
                "similarity": similarity_score
            })
    
    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "date", "url", "description"])
    
    for event in filtered_events:
        writer.writerow([event['name'], event['date'], event['url'], event['description']])
    
    return output.getvalue()


# Example usage:
# Initialize the Event list on LLM start with force refresh then get the event you want
#fetch_events_to_cache(force_refresh=True)
# print(get_eventBrite_events(category_filter="sport"))
# print("-------------------------")
# print(get_eventBrite_events(category_filter="music"))
