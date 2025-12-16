import os
import re
import random
from typing import List, Dict, Optional, Tuple
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage

from toolsFolder.eventBriteTool import get_eventBrite_events_for_llm, fetch_events_to_cache
from toolsFolder.eventBrusselsTool import get_brussels_events_for_llm
from toolsFolder.ticketMasterTool import get_ticketmaster_events_for_llm
from toolsFolder.eventCache import event_cache  # Import global cache


def fetch_all_events_minimal(category: str) -> str:
    """Fetches MINIMAL event data from all sources for LLM selection.
    Returns: [ID] Name | Date | ShortDesc format.
    LLM should pick events by ID based on name and description.
    
    Input category: music, sport, art, culture, theatre, cinema, family, festival, party, nature
    """
    
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
    
    if cat_lower not in mapping:
        return (
            f"CATEGORY_ERROR: La catégorie '{category}' n'est pas reconnue.\n\n"
            f"📋 **Catégories valides :**\n"
            f"• 🎵 music (concerts, festivals)\n"
            f"• 🏃 sport (événements sportifs, fitness)\n"
            f"• 🎨 art (expositions, galeries)\n"
            f"• 🎭 culture (événements culturels)\n"
            f"• 🎪 theatre (théâtre, spectacles)\n"
            f"• 🎬 cinema (films, projections)\n"
            f"• 👨‍👩‍👧 family (activités familiales)\n"
            f"• 🎉 festival (festivals divers)\n"
            f"• 🎊 party (soirées, clubbing)\n"
            f"• 🌳 nature (activités en plein air)\n\n"
            f"💡 **Sois plus explicite !** Utilise l'un de ces termes dans ta recherche."
        )
    
    categoryBru, categoryTM = mapping[cat_lower]
    results = []
    
    # EventBrite
    try:
        print(f"DEBUG: Calling EventBrite with '{categoryTM}'")
        eb_res = get_eventBrite_events_for_llm(category_filter=categoryTM)
        results.append(eb_res)
    except Exception as e:
        print(f"DEBUG: EventBrite error: {e}")
        results.append(f"--- EVENTBRITE ERROR ---\n{str(e)}")

    # Brussels
    try:
        print(f"DEBUG: Calling Brussels with '{categoryBru}'")
        bru_res = get_brussels_events_for_llm(category=categoryBru)
        results.append(bru_res)
    except Exception as e:
        print(f"DEBUG: Brussels error: {e}")
        results.append(f"--- BRUSSELS API ERROR ---\n{str(e)}")

    # TicketMaster
    try:
        print(f"DEBUG: Calling TicketMaster with '{categoryTM}'")
        tm_res = get_ticketmaster_events_for_llm(classificationName=categoryTM)
        results.append(tm_res)
    except Exception as e:
        print(f"DEBUG: TicketMaster error: {e}")
        results.append(f"--- TICKETMASTER ERROR ---\n{str(e)}")
    
    combined = "\n\n".join(results)
    print("FETCHED EVENTS BY LLM:")
    print(combined)
    
    # Add instruction to force using the second tool
    return (
        f"{combined}\n\n"
        f"⚠️ IMPORTANT: Tu as reçu des données MINIMALES (ID, nom, date courte).\n"
        f"Tu DOIS maintenant utiliser l'outil 'Get Event Details' avec les IDs des 5 événements choisis "
        f"pour obtenir les informations complètes (lieu, prix, URL, description).\n"
        f"Exemple: Get Event Details avec input 'abc123,def456,ghi789'"
    )


def get_event_details_by_ids(event_ids: str) -> str:
    """Retrieve full event details from cache by IDs.
    Input: Comma-separated event IDs (e.g., "abc123,def456,ghi789")
    Returns: Full formatted event data for each ID, PRE-FORMATTED with emojis.
    """
    ids = [eid.strip() for eid in event_ids.split(',') if eid.strip()]

    results = []
    for idx, event_id in enumerate(ids, 1):
        event = event_cache.get_event(event_id)
        if event:
            name = event.get('name', 'Unknown')
            
            # Handle date - could be 'date' or 'date_start'
            date = event.get('date') or event.get('date_start') or 'Date inconnue'
            # Clean up ISO date format if needed
            if date and 'T' in str(date):
                date = str(date).replace('T', ' à ').split('+')[0].split('.')[0]
            
            venue = event.get('venue') or 'Lieu non précisé'
            address = event.get('address') or ''
            location = f"{venue} - {address}" if address and address.strip() else venue
            
            price = event.get('price') or 'Prix non précisé'
            if not price or str(price).strip() == '':
                price = 'Prix non précisé'
            
            description = event.get('description') or 'Pas de description disponible'
            # Clean description - remove newlines and limit length
            description = str(description).replace('\n', ' ').replace('\r', ' ').strip()
            if len(description) > 300:
                description = description[:300] + '...'
            
            url = event.get('url') or ''
            # Validate URL
            if url and not str(url).startswith('http'):
                url = 'https://' + str(url) if url else ''
            if not url or str(url).strip() == '':
                url = 'Lien non disponible'
            
            source = event.get('_source', 'unknown').upper()
            
            # PRE-FORMATTED output with emojis - ready for final display
            results.append(
                f"{idx}. **{name}**\n"
                f"📅 {date}\n"
                f"📍 {location}\n"
                f"💰 {price}\n"
                f"🔗 {url}\n"
                f"Description: {description}"
            )
        else:
            results.append(f"{idx}. **Événement non trouvé** (ID: {event_id})")

    output = "\n\n".join(results) if results else "Aucun événement trouvé."
    print("FETCHED EVENT DETAILS BY IDS:")
    print(output)
    
    # Add instruction for final answer
    return (
        f"{output}\n\n"
        f"✅ Voici les détails complets. Retourne ces événements EXACTEMENT comme formatés ci-dessus "
        f"(avec les emojis 📅📍💰🔗 et Description:). Ne modifie pas les URLs ni les informations."
    )


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
        
        # User preferences for ML
        self.user_preferences = {
            'Music': 0.0,
            'Sport': 0.0,
            'Cinema': 0.0,
            'Art': 0.0,
            'Nature': 0.0
        }
        self.interaction_count = 0
        
        self.tools = [
            Tool(
                name="Search_Events",
                func=fetch_all_events_minimal,
                description=(
                    "STEP 1: Search for events. Returns MINIMAL data only: [ID] Name | Date | ShortDescription. "
                    "This gives you a list to choose from. Input: category keyword "
                    "(music, sport, art, theatre, cinema, family, nature, festival, party). "
                    "AFTER using this, you MUST use Get_Event_Details to get full information."
                )
            ),
            Tool(
                name="Get_Event_Details",
                func=get_event_details_by_ids,
                description=(
                    "STEP 2 (MANDATORY): Get FULL details for selected events by their IDs. "
                    "Input: comma-separated event IDs from Search_Events (e.g., 'abc123,def456,ghi789'). "
                    "This returns complete info: venue, address, price, URL, full description. "
                    "You MUST call this before giving your final answer!"
                )
            )
        ]

        self.system_prompt = (
            "Tu es un assistant de recommandation d'événements à Bruxelles.\n\n"
            "**WORKFLOW OBLIGATOIRE EN 2 ÉTAPES:**\n\n"
            "ÉTAPE 1: Utilise 'Search_Events' avec une catégorie → Tu reçois une liste: [ID] Nom | Date | Description courte\n"
            "ÉTAPE 2: Choisis 5 IDs intéressants, puis utilise 'Get_Event_Details' avec ces IDs séparés par des virgules\n"
            "ÉTAPE 3: Tu reçois les détails complets formatés. Retourne-les EXACTEMENT comme reçus.\n\n"
            "**⚠️ RÈGLE ABSOLUE:**\n"
            "- Tu ne peux PAS donner une réponse finale AVANT d'avoir appelé 'Get_Event_Details'\n"
            "- Les données de 'Search_Events' sont INCOMPLÈTES (pas d'adresse, pas d'URL, pas de prix)\n"
            "- Seul 'Get_Event_Details' fournit les informations complètes\n\n"
            "**SÉLECTION:**\n"
            "- Choisis EXACTEMENT 5 événements\n"
            "- Diversifie les sources si possible\n"
            "- Prends les plus pertinents pour la demande de l'utilisateur\n\n"
            "**FORMAT FINAL (fourni par Get_Event_Details):**\n"
            "1. **Nom de l'événement**\n"
            "📅 Date complète\n"
            "📍 Lieu - Adresse\n"
            "💰 Prix\n"
            "🔗 URL complète (https://...)\n"
            "Description: Texte descriptif\n\n"
            "**NE PAS:**\n"
            "❌ Résumer les événements sans appeler Get_Event_Details\n"
            "❌ Inventer des informations (adresse, prix, URL)\n"
            "❌ Modifier le format reçu de Get_Event_Details\n"
        )

        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            system_message=SystemMessage(content=self.system_prompt),
            handle_parsing_errors=True,
            max_iterations=4  # Ensure it has enough iterations for 2 tool calls
        )

    def _detect_profile_context(self, user_message: str) -> str:
        """
        Déduit un profil basique basé sur le message pour les suggestions ML.
        Profiles: Fêtard, Culturel, Sportif, Cinéphile, Chill
        """
        msg = user_message.lower()
        if any(x in msg for x in ['fête', 'soirée', 'boite', 'party', 'danse', 'club', 'sortir']): 
            return "Fêtard"
        if any(x in msg for x in ['musée', 'expo', 'art', 'théâtre', 'spectacle', 'galerie']): 
            return "Culturel"
        if any(x in msg for x in ['sport', 'match', 'courir', 'vélo', 'fitness', 'athlét']): 
            return "Sportif"
        if any(x in msg for x in ['film', 'ciné', 'cinéma', 'projection']): 
            return "Cinéphile"
        if any(x in msg for x in ['parc', 'balade', 'calme', 'nature', 'détente', 'promenade']): 
            return "Chill"
        return "Curieux"

    def _extract_profile_tag(self, user_message: str) -> Tuple[str, str]:
        """Extrait un tag [PROFILE:XXX] au début du message s'il existe."""
        profile = None
        cleaned = user_message
        match = re.match(r"\[PROFILE:([^\]]+)\]\s*(.*)", user_message, flags=re.IGNORECASE)
        if match:
            profile = match.group(1).strip()
            cleaned = match.group(2).strip()
        return profile, cleaned

    def _detect_category_with_llm(self, text: str) -> str:
        """
        Utilise le LLM pour détecter la catégorie d'un texte.
        """
        if not text or len(text) < 3:
            return 'general'
        
        prompt = f"""Classifie ce texte dans UNE SEULE catégorie:
Texte: "{text}"

Catégories disponibles:
- music (concerts, festivals, DJ, orchestres, chorales)
- sport (match, yoga, fitness, randonnée, sport)
- cinema (films, projections, cinéma, documentaires)
- theatre (spectacles, théâtre, pièces)
- art (exposition, musée, galerie, peinture, sculpture)
- nature (parc, balade, jardin, forêt, nature)
- general (autre)

Réponds UNIQUEMENT avec LE MOT DE LA CATÉGORIE (pas d'explication)."""

        try:
            response = self.llm.invoke(prompt)
            category = str(response.content).strip().lower() if hasattr(response, 'content') else str(response).strip().lower()
            for valid_cat in ['music', 'sport', 'cinema', 'theatre', 'art', 'nature', 'general']:
                if valid_cat in category:
                    return valid_cat
            return 'general'
        except Exception as e:
            print(f"[DEBUG LLM] Erreur détection catégorie: {e}")
            return 'general'

    def _update_user_preferences(self, category: str, weight: float = 0.2):
        """Update user preferences based on their searches/interactions."""
        category_mapping = {
            'music': 'Music',
            'party': 'Music',
            'sport': 'Sport',
            'cinema': 'Cinema',
            'theatre': 'Cinema',
            'art': 'Art',
            'nature': 'Nature',
            'family': 'Nature',
        }
        
        ml_category = category_mapping.get(category.lower())
        if ml_category and ml_category in self.user_preferences:
            self.user_preferences[ml_category] = min(1.0, 
                self.user_preferences[ml_category] * 0.8 + weight)
            self.interaction_count += 1
            print(f"[DEBUG ML] Updated preferences: {self.user_preferences}")

    def _generate_ml_suggestion(self, current_results: str, profile: str) -> str:
        """
        Génère une suggestion personnalisée en cherchant le MEILLEUR événement
        parmi les résultats actuels trouvés par l'agent.
        """
        if not current_results or len(current_results) < 50:
            print("[DEBUG ML] Pas assez de résultats pour suggestion ML")
            return ""

        # The results are already formatted, just ask LLM to pick the best one
        prompt = f"""CONTEXTE: L'utilisateur a un profil de type '{profile}'.
TÂCHE: Parmi les événements suivants, lequel est LE MEILLEUR pour lui ?

RÉSULTATS:
{current_results[:3000]}

INSTRUCTION: 
1. Choisis UN SEUL événement de la liste
2. Explique en UNE PHRASE pourquoi ça correspond à son profil
3. RECOPIE l'événement EXACTEMENT comme il est formaté (avec tous les emojis, l'URL complète, etc.)

FORMAT DE RÉPONSE:
🤖 **SUGGESTION PERSONNALISÉE ({profile})**
💡 *[Une phrase courte expliquant le choix]*

1. **[Titre EXACT de l'événement choisi]**
📅 [Date EXACTE]
📍 [Lieu EXACT]
💰 [Prix EXACT]
🔗 [URL EXACTE - ne pas modifier!]
Description: [Description EXACTE]"""

        try:
            response = self.llm.invoke(prompt)
            suggestion = str(response.content) if hasattr(response, 'content') else str(response)
            print(f"[DEBUG ML] Suggestion générée: {suggestion[:100]}...")
            return "\n\n" + suggestion
        except Exception as e:
            print(f"[DEBUG ML] Erreur suggestion personnalisée: {e}")
            return ""

    def _generate_novelty(self, profile: str) -> str:
        """
        Génère la section 'Osez la nouveauté' en cherchant une catégorie opposée
        et en sélectionnant UN vrai événement via LLM.
        """
        opposites = {
            "Fêtard": ["nature", "art"],
            "Sportif": ["art", "theatre"],
            "Culturel": ["sport", "party"],
            "Cinéphile": ["sport", "nature"],
            "Chill": ["party", "sport"],
            "Curieux": ["art", "sport"]
        }
        
        choices = opposites.get(profile, ["art"])
        target_category = random.choice(choices)
        
        print(f"[DEBUG NOVELTY] Profil: {profile} -> Catégorie opposée: {target_category}")
        
        # Get minimal events for the opposite category
        events_minimal = fetch_all_events_minimal(target_category)
        
        if "Aucun événement" in events_minimal or "CATEGORY_ERROR" in events_minimal:
            print(f"[DEBUG NOVELTY] Aucun événement trouvé pour {target_category}")
            return ""

        # Extract IDs from minimal events
        ids = re.findall(r'\[([a-f0-9]{12})\]', events_minimal)
        if not ids:
            print(f"[DEBUG NOVELTY] Aucun ID trouvé dans les événements")
            return ""
        
        # Pick a random event ID (or first few)
        selected_ids = random.sample(ids, min(3, len(ids)))
        
        # Get full details
        full_details = get_event_details_by_ids(','.join(selected_ids))
        
        if "non trouvé" in full_details or not full_details:
            return ""

        # Ask LLM to pick ONE and format it
        format_prompt = f"""Choisis UN événement parmi ceux-ci pour la section "Osez la nouveauté" pour un profil '{profile}'.

ÉVÉNEMENTS DISPONIBLES:
{full_details}

FORMAT DE RÉPONSE (recopie EXACTEMENT les infos de l'événement choisi):
🎲 **OSEZ LA NOUVEAUTÉ !**
💡 *[Une phrase expliquant pourquoi c'est bien de changer]*

1. **[Titre EXACT]**
📅 [Date EXACTE]
📍 [Lieu EXACT]
💰 [Prix EXACT]
🔗 [URL EXACTE]
Description: [Description EXACTE]"""

        try:
            format_response = self.llm.invoke(format_prompt)
            novelty = str(format_response.content) if hasattr(format_response, 'content') else str(format_response)
            print(f"[DEBUG NOVELTY] Générée: {novelty[:100]}...")
            return "\n\n" + novelty
        except Exception as e:
            print(f"[DEBUG NOVELTY] Erreur: {e}")
        
        return ""

    def _add_ml_suggestions_to_response(self, response: str, profile: str) -> str:
        """
        Ajoute les suggestions ML en utilisant des VRAIS événements des APIs.
        """
        enhanced = response
        
        # 1. Suggestion personnalisée (parmi les résultats courants trouvés)
        if "📅" in response and "📍" in response:
            ml_suggestion = self._generate_ml_suggestion(response, profile)
            enhanced += ml_suggestion
        
        # 2. Osez la Nouveauté (chercher une catégorie opposée)
        novelty_section = self._generate_novelty(profile)
        enhanced += novelty_section
        
        return enhanced

    def _force_reformat_with_llm(self, raw_text: str) -> str:
        """Force le reformatage si nécessaire - skip si déjà bien formaté."""
        if not raw_text:
            return raw_text
        
        # Check if already well formatted with full details
        has_emojis = raw_text.count('📅') >= 2 and raw_text.count('📍') >= 2 and raw_text.count('🔗') >= 2
        has_descriptions = 'Description:' in raw_text
        
        if has_emojis and has_descriptions:
            # Already formatted, just clean up
            cleaned = re.sub(r'\[Source: \w+\]', '', raw_text)
            cleaned = re.sub(r'⚠️ IMPORTANT:.*?virgules\)', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'✅ Voici les détails.*?informations\.', '', cleaned, flags=re.DOTALL)
            return cleaned.strip()
        
        # Not properly formatted - needs reformatting
        prompt = f"""Reformate les événements ci-dessous AU FORMAT STRICT. Ne garde que 5 événements max.

Texte à reformater:
{raw_text[:5000]}

RÈGLES DE FORMAT (OBLIGATOIRE):
1. **Titre**
📅 Date
📍 Lieu
💰 Prix (ou 'Gratuit' / 'Prix non précisé')
🔗 URL complète (http/https). Si absente, écrire 'Lien non disponible'
Description: Texte exact et complet

CONTRAINTES:
- Chaque info sur sa propre ligne (pas deux infos sur la même ligne)
- Une ligne vide entre chaque événement
- Garde le texte en français
- Pas d'explications supplémentaires
"""
        try:
            resp = self.llm.invoke(prompt)
            return resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            print(f"[DEBUG] Reformat LLM failed: {e}")
            return raw_text

    def _check_and_fix_incomplete_response(self, response: str, user_query: str) -> str:
        """
        Vérifie si la réponse est incomplète (pas d'adresses, URLs) et la corrige.
        """
        # Check if response has proper formatting with full details
        has_locations = '📍' in response and len(re.findall(r'📍\s*\S+', response)) >= 2
        has_urls = '🔗' in response and ('http' in response or 'Lien non disponible' in response)
        has_descriptions = 'Description:' in response
        
        if has_locations and has_urls and has_descriptions:
            return response  # Already complete
        
        print("[DEBUG] Response incomplete - fetching full details manually...")
        
        # Response is incomplete - the agent didn't call Get_Event_Details
        # Try to detect category and fetch events ourselves
        category = self._detect_category_with_llm(user_query)
        if category == 'general':
            category = 'music'  # Default fallback
        
        # Fetch minimal events
        minimal_events = fetch_all_events_minimal(category)
        
        # Extract first 5 IDs
        ids = re.findall(r'\[([a-f0-9]{12})\]', minimal_events)
        if not ids:
            return response  # No events found, return original
        
        selected_ids = ids[:5]
        
        # Get full details
        full_details = get_event_details_by_ids(','.join(selected_ids))
        
        return full_details

    def _format_response_to_html(self, response: str, category_context: str = "General") -> str:
        """Formate la réponse en HTML avec cartes cliquables et boutons Like (Style Agent.py)"""
        if not response:
            return "<p>...</p>"
        
        if '<ul class="event-list">' in response:
            return '<div class="response-content">\n' + response + '\n</div>'
            
        cleaned = response.replace('```html', '').replace('```', '')
        
        # Remove instruction texts that might have leaked through
        cleaned = re.sub(r'⚠️ IMPORTANT:.*?virgules\)', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'✅ Voici les détails.*?informations\.', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\[Source: \w+\]', '', cleaned)
        
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
        current_event_category = category_context.capitalize() if category_context else "General"
        
        for line in lines:
            line = line.strip()
            
            section_emojis = ['🎯', '📌', '🌟', '🤖', '🎲', '❌', '📭', '💬', '🔄', '🎬', '🎵', '🎨', '🏃', '🌳', '🍳', '🆓', '🎫', '🎭', '🌐', '💡']
            if any(line.startswith(x) for x in section_emojis):
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
                
                event_title = re.sub(r'<[^>]+>', '', content).replace('"', "'")
                
                like_btn = f'<button class="like-btn" data-event-title="{event_title}" data-category="{current_event_category}" onclick="toggleLike(event, this)">❤️</button>'
                
                list_items.append(f'<li class="event-item" onclick="toggleEvent(this)">{like_btn} {content}')
                in_list = True
                continue
            
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
        
        if list_items:
            if current_hidden_info:
                list_items[-1] += f'<div class="more-info">{"".join(current_hidden_info)}</div>'
            list_items[-1] += '<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>'
            html_parts.append('<ul class="event-list">' + ''.join(list_items) + '</ul>')
        
        if current_section:
            html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')

        return '<div class="response-content">\n' + '\n'.join(html_parts) + '\n</div>'

    def _is_activity_search(self, message: str) -> bool:
        """Détecte si le message est une demande d'activités ou une question normale."""
        msg_lower = message.lower().strip()
        
        activity_keywords = [
            'activ', 'événe', 'sortie', 'cherch', 'veux', 'propos', 'trouv',
            'ciné', 'cinema', 'cinéma', 'sport', 'musi', 'musique', 'concert', 'expo', 'théâtre', 'theatre',
            'faire', 'voir', 'cuisine', 'nature', 'gratuit', 'film', 'art', 'show', 'spectacle',
            'match', 'galerie', 'musée', 'atelier', 'cours', 'balade', 'parc',
            'aller', 'jouer', 'danser', 'chanter', 'courir', 'marcher', 'randonn'
        ]
        
        is_activity = any(kw in msg_lower for kw in activity_keywords)
        return is_activity

    def _respond_to_casual_question(self, message: str) -> str:
        """Répond poliment aux questions non-liées aux activités."""
        prompt = f"""Tu es un assistant social bienveillant à Bruxelles. 
L'utilisateur te pose une question qui n'a rien à voir avec les activités/événements.
Réponds poliment, chaleureusement et brièvement en français.

Question: "{message}"

Réponds en 1-2 phrases max, sois naturel et sympa."""

        try:
            response = self.llm.invoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)
            return f'<div class="response-content"><p>{text}</p></div>'
        except Exception as e:
            print(f"[DEBUG] Erreur réponse casual: {e}")
            return '<div class="response-content"><p>Bonjour ! Comment puis-je t\'aider à trouver une activité à Bruxelles ? 😊</p></div>'

    def _category_context_from_message(self, message: str) -> str:
        """Déduit une catégorie normalisée pour les likes (Music/Sport/Cinema/Art/Nature/General)."""
        detected = self._detect_category_with_llm(message)
        mapping = {
            'music': 'Music',
            'sport': 'Sport',
            'cinema': 'Cinema',
            'theatre': 'Cinema',
            'art': 'Art',
            'nature': 'Nature',
        }
        return mapping.get(detected, 'General')

    def chat(self, user_input: str) -> str:
        """
        Main chat interface with ML-enhanced recommendations.
        """
        try:
            # Step 0: Profil optionnel passé via tag [PROFILE:XXX]
            tag_profile, clean_msg = self._extract_profile_tag(user_input)
            
            # Step 1: Vérifier si c'est une demande d'activités
            if not self._is_activity_search(clean_msg):
                print(f"[DEBUG] Question casual détectée: '{clean_msg[:50]}...'")
                return self._respond_to_casual_question(clean_msg)
            
            # Step 2: C'est une demande d'activités
            profile = tag_profile or self._detect_profile_context(clean_msg)
            print(f"[DEBUG] Demande d'activités - Profil détecté: {profile} (tag={tag_profile})")
            category_context = self._category_context_from_message(clean_msg)
            print(f"[DEBUG] Catégorie contexte pour likes: {category_context}")
            
            # Step 3: Exécuter l'agent principal
            raw_response = self.agent.run(input=clean_msg)
            
            # Step 3.1: Check if response is incomplete (missing URLs, addresses)
            raw_response = self._check_and_fix_incomplete_response(raw_response, clean_msg)
            
            # Step 3.2: Forcer le reformatage si nécessaire
            raw_response = self._force_reformat_with_llm(raw_response)
            
            # Step 3.5: Vérifier s'il y a une erreur de catégorie
            if "CATEGORY_ERROR:" in raw_response:
                return self._format_response_to_html(raw_response.replace("CATEGORY_ERROR:", "❌"), category_context)
            
            # Step 4: Ajouter les suggestions ML (avec VRAIS événements)
            enhanced_response = self._add_ml_suggestions_to_response(raw_response, profile)

            # Injecter la catégorie en commentaire pour le parser HTML
            enhanced_response = f"<!-- CATEGORY:{category_context} -->\n" + enhanced_response
            
            # Step 5: Formatter en HTML
            return self._format_response_to_html(enhanced_response, category_context)
            
        except Exception as e:
            print(f"[ERROR] Erreur dans chat(): {e}")
            import traceback
            traceback.print_exc()
            return f"<p>Une erreur est survenue: {str(e)}</p>"