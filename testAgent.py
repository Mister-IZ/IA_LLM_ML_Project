import os
from pydoc import text
import re
import random
from typing import List, Dict, Optional, Tuple
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory

from toolsFolder.eventBriteTool import get_eventBrite_events_for_llm, fetch_events_to_cache
from toolsFolder.eventBrusselsTool import get_brussels_events_for_llm
from toolsFolder.ticketMasterTool import get_ticketmaster_events_for_llm
from toolsFolder.eventCache import event_cache


def fetch_all_events_minimal(category: str) -> str:
    """Fetches MINIMAL event data from all sources."""
    
    mapping = {
        "music": ("concert", "Music"),
        "sport": ("sport", "Sports"),
        "art": ("exhibition", "Arts"),
        "culture": ("exhibition", "Arts"),
        "theatre": ("theatre", "Theatre"),
        "cinema": ("cinema", "Film"),
        "family": ("various", "Family"),
        "festival": ("festival", "Music"), 
        "party": ("clubbing", "Music"),
        "nature": ("various", "Family"),
    }
    
    cat_lower = category.lower().strip()
    
    #If it's one of the main categories we map it to both brussels and ticketmasters correct categories
    if cat_lower in mapping:
        categoryBru, categoryTM = mapping[cat_lower]
    results = []

    
    try:
        eb_res = get_eventBrite_events_for_llm(category_filter=categoryTM)
        results.append(eb_res)
    except Exception as e:
        print(f"DEBUG: EventBrite error: {e}")

    try:
        bru_res = get_brussels_events_for_llm(category=categoryBru)
        results.append(bru_res)
    except Exception as e:
        print(f"DEBUG: Brussels error: {e}")

    try:
        tm_res = get_ticketmaster_events_for_llm(classificationName=categoryTM)
        results.append(tm_res)
    except Exception as e:
        print(f"DEBUG: TicketMaster error: {e}")
    
    return "\n\n".join(results)


def get_full_event_details(event_ids: List[str]) -> List[dict]:
    """Get full event details from cache - NO LLM needed."""
    results = []
    for event_id in event_ids:
        event = event_cache.get_event(event_id.strip())
        if event:
            # Clean up the data
            date = event.get('date') or event.get('date_start') or 'Date inconnue'
            if date and 'T' in str(date):
                date = str(date).replace('T', ' à ').split('+')[0].split('.')[0]
            
            venue = event.get('venue') or 'Lieu non précisé'
            address = event.get('address') or ''
            location = f"{venue} - {address}" if address and address.strip() else venue
            
            url = event.get('url') or ''
            if url and not str(url).startswith('http'):
                url = 'https://' + str(url)
            if not url:
                url = 'Lien non disponible'
            
            description = event.get('description') or 'Pas de description disponible'
            description = str(description).replace('\n', ' ').replace('\r', ' ').strip()[:300]
            
            results.append({
                'name': event.get('name', 'Unknown'),
                'date': date,
                'location': location,
                'price': event.get('price') or 'Prix non précisé',
                'url': url,
                'description': description
            })
    return results


def format_events_to_text(events: List[dict]) -> str:
    """Format events to display text - NO LLM needed."""
    lines = []
    for idx, e in enumerate(events, 1):
        lines.append(
            f"{idx}. **{e['name']}**\n"
            f"📅 {e['date']}\n"
            f"📍 {e['location']}\n"
            f"💰 {e['price']}\n"
            f"🔗 {e['url']}\n"
            f"Description: {e['description']}"
        )
    return "\n\n".join(lines)


class testAgent:
    def __init__(self):
        self.llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0.3,
            mistral_api_key=os.getenv("MISTRAL_API_KEY")
        )

        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            k=5
        )

        self.interaction_count = 0
        
        self.user_preferences = {
            'Music': 0.0, 'Sport': 0.0, 'Cinema': 0.0, 'Art': 0.0, 'Nature': 0.0
        }


    def _detect_category(self, text: str) -> str:
        """Quick category detection - minimal LLM call."""
        prompt = f"""Classifie ce texte dans UNE SEULE catégorie:
        Texte: "{text}"

        Catégories:
        - music (concerts, festivals, DJ, soirées)
        - sport (match, yoga, fitness, randonnée)
        - cinema (films, projections, documentaires)
        - theatre (spectacles, pièces)
        - art (exposition, musée, galerie)
        - nature (parc, balade, jardin)
        - family (enfants, famille)
        - party (clubbing, soirées, nightlife)
        - festival (festivals divers)

        Réponds avec UN SEUL MOT de la liste."""

        try:
            response = self.llm.invoke(prompt)
            cat = str(response.content).strip().lower()
            for valid in ['music', 'sport', 'art', 'cinema', 'theatre', 'nature', 'family', 'party', 'festival']:
                if valid in cat:
                    return valid
        except:
            pass
        #In cas we want to put a specifc category when detection fails
        #Not really needed now because the tools handle incorrect category
        return str(response.content).strip().lower()

    def _select_events_with_llm(self, minimal_events: str, user_query: str) -> List[str]:
        """LLM picks 5 best event IDs - THE ONLY REAL LLM WORK."""
        prompt = f"""Utilisateur cherche: "{user_query}"

Événements disponibles (format: [ID] Nom | Date | Description):
{minimal_events[:3000]}

Tu es un assistant de recommandation d'événements à Bruxelles.
Tu dois TOUJOURS rester poli et professionnel. Si la demande est inappropriée, refuse poliment.
Choisis les 5 meilleurs IDs pour cette demande.
Réponds UNIQUEMENT avec les 5 IDs séparés par des virgules, rien d'autre.
Exemple: abc123,def456,ghi789,jkl012,mno345"""

        try:
            response = self.llm.invoke(prompt)
            ids_text = str(response.content).strip()
            # Extract IDs (12 hex chars)
            ids = re.findall(r'[a-f0-9]{12}', ids_text)
            return ids[:5]
        except Exception as e:
            print(f"[ERROR] LLM selection failed: {e}")
            # Fallback: extract first 5 IDs from minimal_events
            return re.findall(r'\[([a-f0-9]{12})\]', minimal_events)[:5]

    def _detect_profile(self, msg: str) -> str:
        """Simple profile detection - NO LLM."""
        msg = msg.lower()
        if any(x in msg for x in ['fête', 'soirée', 'party', 'club']): return "Fêtard"
        if any(x in msg for x in ['musée', 'expo', 'art', 'théâtre']): return "Culturel"
        if any(x in msg for x in ['sport', 'match', 'fitness']): return "Sportif"
        if any(x in msg for x in ['film', 'ciné', 'cinéma']): return "Cinéphile"
        if any(x in msg for x in ['parc', 'nature', 'balade']): return "Chill"
        return "Curieux"
    
    def _generate_ml_suggestion_light(self, events: List[dict], profile: str) -> str:
        """Generate ML suggestion from the fetched events - NO extra LLM call."""
        if not events:
            return ""
        
        # Simple scoring based on profile keywords
        profile_keywords = {
            "Fêtard": ["party", "club", "dj", "night", "dance", "soirée"],
            "Culturel": ["musée", "expo", "art", "galerie", "culture", "patrimoine"],
            "Sportif": ["sport", "match", "fitness", "run", "vélo", "yoga"],
            "Cinéphile": ["film", "cinema", "projection", "documentaire"],
            "Chill": ["nature", "parc", "balade", "détente", "calme"],
            "Curieux": []
        }
        
        keywords = profile_keywords.get(profile, [])
        best_event = events[0]  # Default to first
        best_score = 0
        
        for event in events:
            score = sum(1 for kw in keywords if kw in (event.get('name', '') + event.get('description', '')).lower())
            if score > best_score:
                best_score = score
                best_event = event
        
        return f"""
        🤖 **SUGGESTION PERSONNALISÉE **
💡 *Recommandé spécialement pour vous !*

1. **{best_event['name']}**
📅 {best_event['date']}
📍 {best_event['location']}
💰 {best_event['price']}
🔗 {best_event['url']}
Description: {best_event['description'][:300]}"""

    def _generate_novelty_light(self, profile: str) -> str:
        """Get a novelty suggestion from cache - NO LLM."""
        opposites = {
            "Fêtard": ["nature", "art"], "Sportif": ["art", "theatre"],
            "Culturel": ["sport", "party"], "Cinéphile": ["sport", "nature"],
            "Chill": ["party", "sport"], "Curieux": ["art", "sport"]
        }
        
        # Get random event from cache
        all_cached = list(event_cache.events.values())
        if not all_cached:
            return ""
        
        event = random.choice(all_cached)
        date = event.get('date') or event.get('date_start', 'Date inconnue')
        
        return f"""

🎲 **OSEZ LA NOUVEAUTÉ !**
💡 *Sortez de votre zone de confort !*

1. **{event.get('name', 'Unknown')}**
📅 {date}
📍 {event.get('venue', 'Lieu non précisé')}
🔗 {event.get('url', 'Lien non disponible')}
Description: {(event.get('description') or '')[:300]}"""

    def _format_to_html(self, response: str, category: str = "General") -> str:
        """Format to HTML - NO LLM needed."""
        if not response:
            return "<p>Aucun événement trouvé.</p>"
        
        # Simple HTML formatting without LLM
        html_parts = ['<div class="response-content">']
        current_event_category = category.capitalize() if category else "General"
        
        lines = response.split('\n')
        in_event = False
        current_hidden_info = []
        
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

             # Section titles (emoji headers)
            if line.startswith('🎲') or line.startswith('🤖'):
                # Close previous event if open
                if in_event:
                    if current_hidden_info:
                        html_parts.append(f'<div class="more-info">{"".join(current_hidden_info)}</div>')
                        current_hidden_info = []
                    html_parts.append('<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>')
                    in_event = False
                html_parts.append(f'<h2 class="section-title">{line}</h2>')
                continue
            
            if line.startswith('💡'):
                html_parts.append(f'<p class="suggestion-hint"><em>{line}</em></p>')
                continue

             # Event title with Like button
            event_match = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', line)
            if event_match:
                # Close previous event
                if in_event:
                    if current_hidden_info:
                        html_parts.append(f'<div class="more-info">{"".join(current_hidden_info)}</div>')
                        current_hidden_info = []
                    html_parts.append('<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>')
                
                event_title = event_match.group(2).replace('"', "'")
                like_btn = f'<button class="like-btn" data-event-title="{event_title}" data-category="{current_event_category}" onclick="toggleLike(event, this)">❤️</button>'
                
                html_parts.append(f'<ul class="event-list"><li class="event-item" onclick="toggleEvent(this)">{like_btn} <strong>{event_title}</strong>')
                in_event = True
                continue
             # Event details
            if in_event:
                if line.startswith('📅') or line.startswith('📍') or line.startswith('💰'):
                    html_parts.append(f'<div class="event-detail">{line}</div>')
                elif line.startswith('🔗'):
                    url_match = re.search(r'(https?://[^\s]+)', line)
                    if url_match:
                        url = url_match.group(1)
                        current_hidden_info.append(f'<div class="event-detail link"><a href="{url}" target="_blank">🔗 Voir le site officiel</a></div>')
                    else:
                        current_hidden_info.append('<div class="event-detail">🔗 Lien non disponible</div>')
                elif line.startswith('Description:'):
                    desc = line.replace('Description:', '').strip()
                    current_hidden_info.append(f'<div class="event-description">📝 {desc}</div>')
        # Close last event
        if in_event:
            if current_hidden_info:
                html_parts.append(f'<div class="more-info">{"".join(current_hidden_info)}</div>')
            html_parts.append('<div class="click-hint">🔽 Cliquez pour voir les détails</div></li></ul>')
        
        html_parts.append('</div>')
        return '\n'.join(html_parts)
        
            
        #     # Event title
        #     if re.match(r'^\d+\.\s+\*\*', line):
        #         title = re.sub(r'^\d+\.\s+\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        #         html_parts.append(f'<div class="event-item">{title}')
        #     elif line.startswith('📅'):
        #         html_parts.append(f'<div class="event-detail">{line}</div>')
        #     elif line.startswith('📍'):
        #         html_parts.append(f'<div class="event-detail">{line}</div>')
        #     elif line.startswith('💰'):
        #         html_parts.append(f'<div class="event-detail">{line}</div>')
        #     elif line.startswith('🔗'):
        #         url_match = re.search(r'(https?://[^\s]+)', line)
        #         if url_match:
        #             url = url_match.group(1)
        #             html_parts.append(f'<div class="event-detail"><a href="{url}" target="_blank">🔗 Voir le site</a></div>')
        #     elif line.startswith('Description:'):
        #         desc = line.replace('Description:', '').strip()
        #         html_parts.append(f'<div class="event-description">📝 {desc}</div></div>')
        #     elif line.startswith('🎲') or line.startswith('🤖'):
        #         html_parts.append(f'<h3>{line}</h3>')
        #     elif line.startswith('💡'):
        #         html_parts.append(f'<p><em>{line}</em></p>')
        
        # html_parts.append('</div>')
        # return '\n'.join(html_parts)

    def _is_activity_search(self, message: str) -> bool:
        """Check if it's an activity search - NO LLM."""
        keywords = ['activ', 'événe', 'sortie', 'concert', 'ciné', 'sport', 'expo', 
                   'théâtre', 'film', 'musée', 'balade', 'faire', 'voir', 'aller']
        return any(kw in message.lower() for kw in keywords)
    def _category_to_ml_key(self, category: str) -> str:
        """Map category to ML preference key."""
        mapping = {
            'music': 'Music', 'party': 'Music', 'festival': 'Music',
            'sport': 'Sport',
            'cinema': 'Cinema', 'theatre': 'Cinema',
            'art': 'Art', 'culture': 'Art',
            'nature': 'Nature', 'family': 'Nature'
        }
        return mapping.get(category.lower(), 'Music')

    def chat(self, user_input: str) -> str:
        """
        OPTIMIZED: Only 2 LLM calls max per request.
        1. Detect category (tiny prompt)
        2. Select 5 IDs (medium prompt)
        Everything else is code!
        """
        try:
            # Check if it's an activity search
            if not self._is_activity_search(user_input):
                # Simple response - 1 small LLM call
                response = self.llm.invoke(f"Réponds brièvement en français: {user_input}")
                return f'<div class="response-content"><p>{response.content}</p></div>'
            
            # STEP 1: ALWAY DO THIS STEP FIRST -   Detect category
            category = self._detect_category(user_input)
            print(f"[DEBUG] Category: {category}")

            # Get ML category for likes
            category_context = self._category_to_ml_key(category)
            
            
            # STEP 2: Fetch minimal events (NO LLM - just API/cache)
            minimal_events = fetch_all_events_minimal(category)
            if not minimal_events:
                return '<div class="response-content"><p>Aucun événement trouvé pour cette catégorie.</p></div>'
            
            # STEP 3: LLM selects 5 IDs (1 LLM call ~500 tokens)
            selected_ids = self._select_events_with_llm(minimal_events, user_input)
            print(f"[DEBUG] Selected IDs: {selected_ids}")
            
            if not selected_ids:
                return '<div class="response-content"><p>Aucun événement correspondant trouvé.</p></div>'
            
            # STEP 4: Get full details from cache (NO LLM!)
            full_events = get_full_event_details(selected_ids)
            
            # STEP 5: Format to text (NO LLM!)
            formatted_text = format_events_to_text(full_events)
            
            # STEP 6: Add novelty from cache (NO LLM!)
            profile = self._detect_profile(user_input)
            novelty = self._generate_novelty_light(profile)
            formatted_text += novelty

            # STEP 6b: Add ML suggestion (NO LLM!)
            ml_suggestion = self._generate_ml_suggestion_light(full_events, profile)
            formatted_text += ml_suggestion
            
            # STEP 7: Format to HTML (NO LLM!)
            return self._format_to_html(formatted_text, category)
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            return f"<p>Erreur: {str(e)}</p>"