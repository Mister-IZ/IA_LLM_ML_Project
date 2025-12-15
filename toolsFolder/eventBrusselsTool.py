import requests
import csv
import io


def get_brussels_events(category: str) -> str:
    """Fetch events from Brussels API in French as CSV.
    
    Args:
        category (str): Event category: 'Concerts', 'Spectacles', 'Expositions', 'Théâtre', 'Clubbing', 'Cinéma', 'Sports'
    
    Returns:
        str: CSV string with event data.
    """
    
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

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    all_events = response.json()["response"]["results"]["event"]
    
    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "date_start", "date_end", "venue", "address", "price", "description", "url"])
    
    for event in all_events:
        if 'fr' in event['translations']:
            fr = event['translations']['fr']
            place_fr = event['place']['translations']['fr']
            
            writer.writerow([
                fr.get('name'),
                event.get('date_start'),
                event.get('date_end'),
                place_fr.get('name'),
                f"{place_fr.get('address_line1')}, {place_fr.get('address_zip')} {place_fr.get('address_city')}",
                "Gratuit" if event.get('is_free') else "Payant",
                (fr.get('longdescr') or fr.get('shortdescr') or "").replace('\n', ' ')[:200],
                fr.get('agenda_url') or fr.get('website') or place_fr.get('website')
            ])
    
    return output.getvalue()

# Exemple usage:
# csv_data = get_brussels_events('concert')
# print(csv_data)