import os
import re
from typing import List, Dict, Optional, Tuple
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage


from toolsFolder.eventBriteTool import (get_eventBrite_events, fetch_events_to_cache)
from toolsFolder.eventBrusselsTool import get_brussels_events
from toolsFolder.ticketMasterTool import get_ticketmaster_events
from toolsFolder.helper import BrusselsToTMDict
from recommender import SocialRecommender

def fetch_all_events(category: str) -> str:
    """Fetches events from all available sources (EventBrite, Brussels API, TicketMaster).
    Input category is a generic keyword like 'music', 'sport', 'art', 'theatre', 'cinema'.
    ONLY USE THE CATEGORIES DEFINED IN THE DOCSTRING BELOW.
    music, sport, art, culture, theatre, cinema, family, festival, party
    """
    
    # Mapping logic: Generic Category -> (Brussels Category, TicketMaster Classification)
    # Brussels options: 'concert', 'show', 'exhibition', 'theatre', 'clubbing', 'cinema', 'sport', 'festival'
    # TicketMaster options: 'Music', 'Sports', 'Arts & Theatre', 'Film', 'Family'
    
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
        "nature": ("various", "Family"),  # Nature events often classified as family/outdoor
    }
    
    cat_lower = category.lower().strip()
    
    if cat_lower in mapping:
        categoryBru, categoryTM = mapping[cat_lower]
    else:
        # Default fallback if not found in map
        categoryBru = category
        categoryTM = category
        
    results = []
    
    # EventBrite (uses raw query as filter)
    try:
        print(f"DEBUG: Calling EventBrite with '{categoryTM}'")
        eb_res = get_eventBrite_events(category_filter=categoryTM)
        results.append(f"--- EVENTBRITE EVENTS ---\n{eb_res}")
    except Exception as e:
        print(f"DEBUG: EventBrite error: {e}")
        results.append(f"--- EVENTBRITE ERROR ---\n{str(e)}")

    # Brussels
    try:
        print(f"DEBUG: Calling Brussels with '{categoryBru}'")
        bru_res = get_brussels_events(category=categoryBru)
        results.append(f"--- BRUSSELS API EVENTS ---\n{bru_res}")
    except Exception as e:
        print(f"DEBUG: Brussels error: {e}")
        results.append(f"--- BRUSSELS API ERROR ---\n{str(e)}")

    # TicketMaster
    try:
        print(f"DEBUG: Calling TicketMaster with '{categoryTM}'")
        tm_res = get_ticketmaster_events(classificationName=categoryTM)
        results.append(f"--- TICKETMASTER EVENTS ---\n{tm_res}")
    except Exception as e:
        print(f"DEBUG: TicketMaster error: {e}")
        results.append(f"--- TICKETMASTER ERROR ---\n{str(e)}")
        
    return "\n\n".join(results)


class NewAgent:
    def __init__(self):
        self.llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0.3,
            mistral_api_key=os.getenv("MISTRAL_API_KEY")
        )

        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10
        )
        
        # === ML MODEL: K-Nearest Neighbors for user profiling ===
        try:
            self.recommender = SocialRecommender()
            print("🤖 ML Recommender initialized successfully")
        except FileNotFoundError as e:
            print(f"⚠️ ML Recommender not available: {e}")
            self.recommender = None
        
        # === USER PREFERENCE STATE (accumulated from interactions) ===
        # These weights are updated based on user searches and likes
        self.user_preferences = {
            "Music": 0.0,
            "Sport": 0.0,
            "Cinema": 0.0,
            "Art": 0.0,
            "Nature": 0.0,
        }
        self.interaction_count = 0  # Track interactions to normalize preferences
        
        self.tools = [
            Tool(
                name="Unified Events Fetcher",
                func=fetch_all_events,
                description="Fetch events from ALL sources (EventBrite, Brussels API, TicketMaster) at once. Input should be a generic category keyword like 'music', 'sport', 'art', 'theatre', 'cinema', 'family', 'nature'."
            )
        ]

        self.system_prompt = (
            "You are an event recommendation assistant. Use the 'Unified Events Fetcher' tool to find events. "
            "This tool returns events from multiple sources. "
            "Analyze the results from ALL sources and select the 5 BEST events to recommend to the user. "
            "Ensure you pick a diverse set of events if possible. IF POSSIBLE 2 FROM BRUSSELS API, 2 FROM TICKETMASTER AND 1 FROM EVENTBRITE. "
            "\n\n"
            "**FORMAT DE RÉPONSE STRICT :**\n"
            "1. **Nom de l'événement**\n"
            "📅 Date\n"
            "📍 Lieu\n"
            "💰 Prix\n"
            "🔗 Lien\n"
            "Description: Texte exact\n\n"
            "Utilise des emojis (📅, 📍, 💰, 🔗) pour structurer l'information. "
            "IMPORTANT: Si un lien (URL) est disponible dans les données, tu DOIS l'inclure après l'emoji 🔗."
        )


        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            system_message=SystemMessage(content=self.system_prompt)
        )

    def _detect_category_with_llm(self, user_message: str) -> str:
        """
        🌱 GREEN APPROACH: Use the LLM to detect the category from user intent.
        This is more ecological than keyword matching because:
        1. Single inference call instead of multiple regex/keyword checks
        2. Better accuracy = fewer retry API calls
        3. Understands context and nuance
        """
        prompt = f"""Classify this user request into ONE category for event search.
        
User message: "{user_message}"

Categories (choose exactly ONE):
- Music (concerts, festivals, DJ, live music)
- Sport (sports events, yoga, fitness, running, matches)
- Cinema (films, movies, screenings, projections)
- Art (exhibitions, museums, galleries, paintings)
- Nature (outdoor, parks, walks, gardens, hiking)
- Theatre (plays, shows, comedy, drama)
- Party (clubbing, nightlife, bars)
- Family (family-friendly, kids activities)
- General (if unclear or mixed)

Reply with ONLY the category name, nothing else."""

        try:
            response = self.llm.invoke(prompt)
            category = response.content.strip().lower() if hasattr(response, 'content') else str(response).strip().lower()
            
            # Map to valid categories
            valid_categories = ['music', 'sport', 'cinema', 'art', 'nature', 'theatre', 'party', 'family', 'general']
            for valid in valid_categories:
                if valid in category:
                    print(f"[DEBUG LLM Category] Detected: {valid} from message: '{user_message[:50]}...'")
                    return valid
            
            return 'general'
        except Exception as e:
            print(f"[DEBUG] LLM category detection error: {e}")
            return 'general'

    def _update_user_preferences(self, category: str, weight: float = 0.2):
        """
        Update user preferences based on their searches/interactions.
        Uses exponential moving average for smooth preference learning.
        """
        # Map detected category to ML feature columns
        category_mapping = {
            'music': 'Music',
            'party': 'Music',
            'sport': 'Sport',
            'cinema': 'Cinema',
            'theatre': 'Cinema',  # Theatre is similar to Cinema in our model
            'art': 'Art',
            'nature': 'Nature',
            'family': 'Nature',  # Family activities often outdoor
        }
        
        ml_category = category_mapping.get(category.lower())
        if ml_category and ml_category in self.user_preferences:
            # Exponential moving average update
            self.user_preferences[ml_category] = min(1.0, 
                self.user_preferences[ml_category] * 0.8 + weight)
            self.interaction_count += 1
            print(f"[DEBUG ML] Updated preferences: {self.user_preferences}")

    def _get_ml_recommendation(self) -> Optional[Dict]:
        """
        Get personalized recommendation using K-NN model.
        Returns the matched user profile and suggested activity type.
        """
        if not self.recommender or self.interaction_count < 2:
            return None  # Need at least 2 interactions to make meaningful recommendation
        
        try:
            result = self.recommender.find_similar_user(self.user_preferences)
            print(f"[DEBUG ML] K-NN match: {result}")
            return result
        except Exception as e:
            print(f"[DEBUG ML] K-NN error: {e}")
            return None

    def _get_routine_breaker(self) -> Optional[Dict]:
        """
        Get 'anti-routine' suggestion based on user's lowest category.
        Encourages exploration of new activity types.
        """
        if not self.recommender or self.interaction_count < 3:
            return None
        
        try:
            result = self.recommender.find_routine_breaker(self.user_preferences)
            print(f"[DEBUG ML] Routine breaker: {result}")
            return result
        except Exception as e:
            print(f"[DEBUG ML] Routine breaker error: {e}")
            return None

    def _add_ml_suggestions_to_response(self, response: str) -> str:
        """
        Append ML-based suggestions to the response if available.
        """
        additions = []
        
        # Get K-NN recommendation
        ml_rec = self._get_ml_recommendation()
        if ml_rec:
            additions.append(
                f"\n\n🤖 **SUGGESTION PERSONNALISÉE**\n"
                f"💡 Basé sur votre profil ({ml_rec['matched_archetype']}), "
                f"vous pourriez aussi aimer: **{ml_rec['recommended_activity_type']}**\n"
                f"(Similarité: {ml_rec['similarity_score']*100:.0f}%)"
            )
        
        # Get routine breaker suggestion
        routine = self._get_routine_breaker()
        if routine:
            additions.append(
                f"\n\n🎲 **OSEZ LA NOUVEAUTÉ !**\n"
                f"💡 {routine['reason']}\n"
                f"Essayez: **{routine['activity_type']}** (style {routine['archetype']})"
            )
        
        if additions:
            response += "".join(additions)
        
        return response

    def _format_response_to_html(self, response: str, category_context: str = "General") -> str:
        """Formate la réponse en HTML avec cartes cliquables et boutons Like (Style Agent.py)"""
        if not response:
            return "<p>...</p>"
        
        # Si déjà du HTML
        if '<ul class="event-list">' in response:
            return '<div class="response-content">\n' + response + '\n</div>'
            
        cleaned = response.replace('```html', '').replace('```', '')
        
        # Normalisation des sauts de ligne pour le parsing
        patterns_to_normalize = [
            (r'\s+(\d+\.\s+\*\*)', r'\n\1'),
            (r'\s+📅', '\n📅'),
            (r'\s+📍', '\n📍'),
            (r'\s+💰', '\n💰'),
            (r'\s+🔗', '\n🔗'),
            (r'\s+Description:', '\nDescription:'),
        ]
        
        for pattern, replacement in patterns_to_normalize:
            cleaned = re.sub(pattern, replacement, cleaned)
            
        html_parts = []
        lines = cleaned.split('\n')
        
        current_section = []
        in_list = False
        list_items = []
        current_hidden_info = []
        # Capitalize category to match ML vector keys (Music, Sport, Cinema, Art, Nature)
        current_event_category = category_context.capitalize() if category_context else "General"
        
        for line in lines:
            line = line.strip()
            
            # Titres de section (Emojis)
            section_emojis = ['🎯', '📌', '🌟', '🤖', '🎲', '❌', '📭', '💬', '🔄', '🎬', '🎵', '🎨', '🏃', '🌳', '🍳', '🆓', '🎫', '🎭', '🌐']
            if any(line.startswith(x) for x in section_emojis):
                # Fermer la liste précédente si nécessaire
                if list_items:
                    if current_hidden_info:
                        list_items[-1] += f'<div class="more-info">{"".join(current_hidden_info)}</div>'
                        current_hidden_info = []
                    list_items[-1] += '<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>'
                    html_parts.append('<ul class="event-list">' + ''.join(list_items) + '</ul>')
                    list_items = []
                    in_list = False
                
                if current_section:
                    html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')
                    current_section = []
                
                html_parts.append(f'<h2 class="section-title">{line}</h2>')
                continue
            
            # Item Liste (1. **Nom**)
            event_match = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', line) or re.match(r'^(\d+)\.\s+([A-Z].+)', line)
            if event_match:
                if list_items:
                    if current_hidden_info:
                        list_items[-1] += f'<div class="more-info">{"".join(current_hidden_info)}</div>'
                        current_hidden_info = []
                    list_items[-1] += '<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>'
                
                if not in_list:
                    if current_section:
                        html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')
                        current_section = []
                
                content = re.sub(r'^\d+\.\s+', '', line)
                content = content.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                
                # Extract clean event title for data attribute (remove HTML tags)
                event_title = re.sub(r'<[^>]+>', '', content).replace('"', "'")
                
                # Bouton Like with event title and category data
                like_btn = f'<button class="like-btn" data-event-title="{event_title}" data-category="{current_event_category}" onclick="toggleLike(event, this)">❤️</button>'
                
                list_items.append(f'<li class="event-item" onclick="toggleEvent(this)">{like_btn} {content}')
                in_list = True
                continue
            
            # Détails
            if in_list:
                if any(line.startswith(x) for x in ['📅', '📍', '💰', '🆓']):
                    line_clean = line.replace('**', '')
                    list_items[-1] += f'<div class="event-detail">{line_clean}</div>'
                elif line.startswith('🔗'):
                    url = None
                    if 'http' in line:
                        found = re.search(r'(https?://[^\s\)]+)', line)
                        if found:
                            url = found.group(1)
                    
                    if url:
                        current_hidden_info.append(f'<div class="event-detail link"><a href="{url}" target="_blank">🔗 Voir le site officiel</a></div>')
                    else:
                        current_hidden_info.append('<div class="event-detail">🔗 Lien non disponible</div>')
                elif line.startswith('Description:'):
                    desc = line.replace('Description:', '').strip()
                    current_hidden_info.append(f'<div class="event-description">📝 {desc}</div>')
                elif line:
                    current_hidden_info.append(f'<div class="event-info">{line}</div>')
            elif line:
                current_section.append(line)
        
        # Fermetures finales
        if list_items:
            if current_hidden_info:
                list_items[-1] += f'<div class="more-info">{"".join(current_hidden_info)}</div>'
            list_items[-1] += '<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>'
            html_parts.append('<ul class="event-list">' + ''.join(list_items) + '</ul>')
        
        if current_section:
            html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')

        return '<div class="response-content">\n' + '\n'.join(html_parts) + '\n</div>'

    def chat(self, user_input: str) -> str:
        """
        Main chat interface with ML-enhanced recommendations.
        
        🌱 GREEN APPROACH:
        1. Use LLM to detect category (single call, better accuracy)
        2. Update user preferences based on detected category
        3. Get personalized ML recommendations after enough interactions
        4. All in a single flow - no redundant API calls
        """
        # Step 1: Detect category using LLM (green: one inference for accurate classification)
        detected_category = self._detect_category_with_llm(user_input)
        
        # Step 2: Update user preferences for ML model
        if detected_category != 'general':
            self._update_user_preferences(detected_category, weight=0.3)
        
        # Step 3: Run the agent to get events
        raw_response = self.agent.run(input=user_input)
        
        # Step 4: Add ML suggestions if user has enough interactions
        enhanced_response = self._add_ml_suggestions_to_response(raw_response)
        
        # Step 5: Format to HTML with category context for like button
        # Map detected category to ML category for like tracking
        category_mapping = {
            'music': 'Music', 'party': 'Music',
            'sport': 'Sport',
            'cinema': 'Cinema', 'theatre': 'Cinema',
            'art': 'Art',
            'nature': 'Nature', 'family': 'Nature',
            'general': 'General'
        }
        ml_category = category_mapping.get(detected_category, 'General')
        
        return self._format_response_to_html(enhanced_response, ml_category)

    def like_event(self, category: str):
        """
        Called when user likes an event. Boosts that category in preferences.
        This allows the ML model to learn from explicit user feedback.
        """
        self._update_user_preferences(category, weight=0.5)  # Higher weight for explicit likes
        print(f"[DEBUG ML] User liked event in category: {category}")

    def reset_preferences(self):
        """Reset user preferences (new session)."""
        self.user_preferences = {
            "Music": 0.0,
            "Sport": 0.0,
            "Cinema": 0.0,
            "Art": 0.0,
            "Nature": 0.0,
        }
        self.interaction_count = 0
        self.memory.clear()
        print("[DEBUG ML] User preferences reset")