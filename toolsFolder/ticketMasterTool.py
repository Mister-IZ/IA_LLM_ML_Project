import requests
import csv
import os
import io
from dotenv import load_dotenv

load_dotenv(override=True)

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_CONSUMER_KEY")

def get_ticketmaster_events(classificationName: str) -> str:
    """Fetch events from Ticketmaster API as CSV.
    
    Args:
        classificationName (str): Event type filter: 'Music', 'Sports', 'Arts', 'Family', etc.
    
    Returns:
        str: CSV string with event data.
    """
    print(f"DEBUG: get_ticketmaster_events called with classificationName='{classificationName}'")
    
    if not TICKETMASTER_API_KEY:
        return "ERROR: Missing TICKETMASTER_CONSUMER_KEY in environment (.env)"
    
    url = 'https://app.ticketmaster.com/discovery/v2/events.json'
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'countryCode': 'BE',
        'size': 25,
        'sort': 'date,asc',
        'city': 'Brussels',
        'classificationName': classificationName
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "date", "venue", "address", "price_min", "price_max", "currency", "url"])
    
    events = data.get('_embedded', {}).get('events', [])
    
    for event in events:
        venue_data = event.get('_embedded', {}).get('venues', [{}])[0]
        price_min, price_max, currency = None, None, "EUR"
        if 'priceRanges' in event and event['priceRanges']:
            pr = event['priceRanges'][0]
            price_min = pr.get('min')
            price_max = pr.get('max')
            currency = pr.get('currency', 'EUR')
        
        writer.writerow([
            event['name'],
            event['dates']['start'].get('dateTime', event['dates']['start'].get('localDate')),
            venue_data.get('name'),
            venue_data.get('address', {}).get('line1'),
            price_min,
            price_max,
            currency,
            event['url']
        ])
    
    return output.getvalue()

#exemple usage:
# csv_data = get_ticketmaster_events('Music')
# print(csv_data)