import os
import re
from typing import List, Dict, Optional, Tuple
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage

# Import des fonctions optimisées
from tools import (
    get_brussels_events_formatted,
    get_brussels_events_formatted_with_all,
    get_brussels_events,
    get_ticketmaster_events, 
    get_eventbrite_events,
    get_brussels_api,
    EventFilter
)


class SocialAgentLangChain:
    def __init__(self):
        self.llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0.3,
            mistral_api_key=os.getenv("MISTRAL_API_KEY")
        )
        
        # === STATE MANAGEMENT (comme ton ancien code) ===
        self.current_state = {
            "filter_type": None,
            "current_page": 1,
            "all_events": [],
            "last_displayed_events": [],  # Événements formatés affichés
            "last_ml_category": "General"
        }
        
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10
        )
        
        self.tools = self._setup_tools()
        
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_message": SystemMessage(content=self._get_system_prompt()),
                "extra_prompt_messages": [MessagesPlaceholder(variable_name="chat_history")]
            }
        )
    
    def _get_system_prompt(self):
        return """Tu es un assistant social bienveillant à Bruxelles. Tu aides les gens à trouver des activités.

**RÈGLES STRICTES :**
1. Pour les demandes d'activités → utilise les outils de recherche
2. Pour les questions sur un événement déjà affiché → réponds directement
3. NE PAS reformuler ou résumer les événements - recopie les infos exactes
4. GARDE le format multi-ligne avec les emojis (📅, 📍, 💰, 🔗)

**FORMAT DE RÉPONSE POUR LES ÉVÉNEMENTS :**
1. **Nom de l'événement**
📅 Date
📍 Lieu
💰 Prix
🔗 Lien
Description: Texte exact

Sois empathique et naturel dans tes réponses conversationnelles."""

    def _setup_tools(self):
        def recherche_brussels(query: str) -> str:
            """Recherche sur Brussels API avec state update"""
            print(f"[DEBUG Tool] Recherche Brussels: '{query}'")
            
            # Reset page si nouvelle recherche
            self.current_state["current_page"] = 1
            
            # Obtenir les résultats
            result_text, ml_category, formatted_events = get_brussels_events_formatted(query)
            
            # Sauvegarder dans le state
            self.current_state["last_displayed_events"] = formatted_events
            self.current_state["last_ml_category"] = ml_category
            self.current_state["filter_type"], _, _ = EventFilter.detect_filter_type(query)
            
            return result_text
        
        def recherche_ticketmaster(query: str) -> str:
            """Recherche sur Ticketmaster"""
            q = query.lower()
            
            if 'sport' in q:
                cat = 'Sports'
            elif 'art' in q or 'theatre' in q or 'spectacle' in q:
                cat = 'Arts & Theatre'
            elif 'cinema' in q or 'film' in q:
                cat = 'Film'
            else:
                cat = 'Music'
            
            return get_ticketmaster_events(cat, genre_filter=None)
        
        def recherche_eventbrite(query: str) -> str:
            """Recherche sur EventBrite"""
            return get_eventbrite_events()

        return [
            Tool(
                name="BrusselsAPI", 
                func=recherche_brussels, 
                description="Recherche TOUTES les activités à Bruxelles: concerts, films, art, sport, cuisine, nature, gratuit. Toujours essayer cet outil en premier."
            ),
            Tool(
                name="TicketmasterAPI", 
                func=recherche_ticketmaster, 
                description="Pour les grands concerts internationaux et événements sportifs."
            ),
            Tool(
                name="EventBriteAPI", 
                func=recherche_eventbrite, 
                description="Pour les ateliers et événements sociaux."
            )
        ]

    def reset_conversation(self):
        """Réinitialise la conversation et le state"""
        self.current_state = {
            "filter_type": None,
            "current_page": 1,
            "all_filtered_events": [],  # TOUS les événements filtrés (pour pagination locale)
            "last_displayed_events": [],  # Événements affichés sur la page actuelle
            "last_ml_category": "General",
            "last_search_query": None
        }
        self.memory.clear()

    def _is_pagination_request(self, message: str) -> bool:
        """Détecte si c'est une demande de pagination"""
        return message.lower().strip() in ['autre', 'autres', 'suivant', 'encore', 'plus', 'next']

    def _handle_pagination(self) -> str:
        """Gère la pagination des résultats - PAGINATION LOCALE (rapide!)"""
        all_events = self.current_state.get("all_filtered_events", [])
        
        if not all_events:
            return self._format_response_to_html(
                "🔍 Fais d'abord une recherche pour voir des résultats !",
                "General"
            )
        
        # Incrémenter la page
        self.current_state["current_page"] += 1
        page = self.current_state["current_page"]
        limit = 8
        
        # Calculer les indices
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        print(f"[DEBUG] Pagination LOCALE page {page}: events[{start_idx}:{end_idx}] sur {len(all_events)} total")
        
        # Extraire la page
        page_events = all_events[start_idx:end_idx]
        
        if not page_events:
            # Revenir à la page 1
            self.current_state["current_page"] = 1
            return self._format_response_to_html(
                "📭 **Plus d'activités de ce type.**\n\n🎯 Essaie une autre catégorie !",
                self.current_state["last_ml_category"]
            )
        
        # Sauvegarder les événements affichés
        self.current_state["last_displayed_events"] = page_events
        
        # Reconstruire le texte
        ml_category = self.current_state["last_ml_category"]
        filter_type, emoji, _ = EventFilter.detect_filter_type(self.current_state.get("last_search_query", ""))
        
        result = f"{emoji} **ACTIVITÉS À BRUXELLES :**\n\n"
        for i, event in enumerate(page_events, 1):
            result += f"{i}. **{event['title']}**\n"
            result += f"📅 {event['start_date']}\n"
            result += f"📍 {event['location']}\n"
            result += f"💰 {event['price']}\n"
            if event.get('url'):
                result += f"🔗 {event['url']}\n"
            result += f"Description: {event['description']}\n"
            result += f"<!-- CATEGORY:{ml_category} -->\n\n"
        
        total_pages = (len(all_events) // limit) + 1
        result += f"\n💬 **{len(page_events)} activités affichées** (Page {page}/{total_pages})\n"
        result += '<div class="pagination-hint">🔄 Tu veux que je t\'en propose d\'autres ? <button class="suggestion-btn pagination-btn" onclick="handlePagination()">👉 Appuie ici</button></div>'
        
        return self._format_response_to_html(result, ml_category)

    def chat(self, message_complexe: str) -> str:
        """Interface de chat principale avec gestion intelligente"""
        
        # 1. Extraction User Message vs System Instruction (ML)
        user_message = message_complexe.split("[SYSTEM_HIDDEN_INSTRUCTION")[0].strip()
        system_instruction = ""
        if "[SYSTEM_HIDDEN_INSTRUCTION" in message_complexe:
            system_instruction = message_complexe.split("[SYSTEM_HIDDEN_INSTRUCTION")[1].replace("]", "")
        
        msg_lower = user_message.lower().strip()
        
        # 2. Détection du contexte pour le ML
        current_context_category = "General"
        filter_type, _, ml_cat = EventFilter.detect_filter_type(user_message)
        if ml_cat != "General":
            current_context_category = ml_cat
        
        # 3. Gestion de la pagination
        if self._is_pagination_request(user_message):
            return self._handle_pagination()
        
        # 4. Gestion du retour à la liste
        if msg_lower in ['retour', 'liste', 'back']:
            if self.current_state["last_displayed_events"]:
                return self._rebuild_list_from_state()
            else:
                return self._format_response_to_html(
                    "🔍 Pas de liste précédente. Fais une nouvelle recherche !",
                    current_context_category
                )
        
        # 6. Est-ce une recherche d'activités ?
        search_keywords = ['activ', 'événe', 'sortie', 'cherch', 'veux', 'propos', 'trouv', 
                          'ciné', 'sport', 'musi', 'concert', 'expo', 'théâtre', 'faire', 
                          'voir', 'cuisine', 'nature', 'gratuit', 'film', 'art']
        is_search = any(kw in msg_lower for kw in search_keywords)
        
        # Si PAS de recherche → Mode Discussion
        if not is_search:
            raw_response = self.agent.run(user_message)
            return self._format_response_to_html(raw_response, current_context_category)
        
        # 7. Mode Recherche avec ML
        results = []
        
        # Sauvegarder la recherche pour la pagination
        self.current_state["last_search_query"] = user_message
        self.current_state["filter_type"] = filter_type
        self.current_state["current_page"] = 1  # Reset page pour nouvelle recherche
        
        print(f"[DEBUG] Nouvelle recherche: '{user_message}', filter_type: {filter_type}")
        
        # Toujours essayer Brussels d'abord
        try:
            result_text, ml_category, formatted_events, all_events = get_brussels_events_formatted_with_all(
                user_message
            )
            if formatted_events:
                results.append(result_text)
                self.current_state["last_displayed_events"] = formatted_events
                self.current_state["all_filtered_events"] = all_events  # STOCKER TOUS pour pagination locale
                self.current_state["last_ml_category"] = ml_category
                current_context_category = ml_category
                print(f"[DEBUG] Stocké {len(all_events)} événements pour pagination locale")
        except Exception as e:
            print(f"[DEBUG] Erreur Brussels: {e}")
            import traceback
            traceback.print_exc()
        
        # Appel conditionnel Ticketmaster (concerts/sports)
        if any(x in msg_lower for x in ['concert', 'musique', 'music', 'sport', 'match']):
            try:
                result_tm = get_ticketmaster_events("Music" if 'concert' in msg_lower else "Sports")
                if result_tm and "Aucun" not in result_tm:
                    results.append(result_tm)
            except:
                pass
        
        content_found = "\n\n".join([r for r in results if r and "Aucun" not in r and "Erreur" not in r])
        
        if not content_found:
            return self._format_response_to_html(
                f"❌ Aucune activité trouvée pour '{user_message}'.\n\n💡 Essaie une autre recherche !",
                current_context_category
            )
        
        # 8. Ajouter les suggestions ML si présentes
        if system_instruction:
            content_found = self._add_ml_suggestions(content_found, system_instruction, current_context_category)
        
        return self._format_response_to_html(content_found, current_context_category)

    def _rebuild_list_from_state(self) -> str:
        """Reconstruit la liste à partir du state"""
        events = self.current_state["last_displayed_events"]
        ml_category = self.current_state["last_ml_category"]
        
        result = "🎯 **ACTIVITÉS PRÉCÉDENTES :**\n\n"
        
        for i, event in enumerate(events, 1):
            result += f"{i}. **{event['title']}**\n"
            result += f"📅 {event['start_date']}\n"
            result += f"📍 {event['location']}\n"
            result += f"💰 {event['price']}\n"
            if event.get('url'):
                result += f"🔗 {event['url']}\n"
            result += f"Description: {event['description']}\n\n"
        
        result += "🔄 Dis 'autre' pour plus d'options"
        
        return self._format_response_to_html(result, ml_category)

    def _get_opposite_events(self, system_instruction: str, current_category: str) -> Optional[str]:
        """Recherche des événements 'Osez la Nouveauté' avec logique LLM intelligente"""
        
        # Détecter le profil
        profile = "Fêtard"
        for prof in ['Fêtard', 'Culturel', 'Sportif', 'Cinéphile', 'Chill']:
            if prof in system_instruction:
                profile = prof
                break
        
        events = self.current_state.get("last_displayed_events", [])
        if not events:
            return None
        
        # Mapping des profils vers les catégories LARGES possibles pour "Osez la Nouveauté"
        category_mapping = {
            'Fêtard': ['sport', 'nature', 'art'],  # Fêtard peut découvrir le calme
            'Culturel': ['musique', 'sport', 'nature'],  # Culturel peut découvrir la musique live ou l'action
            'Sportif': ['art', 'musique', 'spectacle'],  # Sportif peut découvrir la créativité
            'Cinéphile': ['sport', 'musique', 'spectacle'],  # Cinéphile peut découvrir d'autres formes d'art
            'Chill': ['musique', 'spectacle', 'art'],  # Chill peut découvrir l'énergie
        }
        
        available_categories = category_mapping.get(profile, ['sport', 'musique', 'art'])
        
        # Construire la liste des événements actuels pour contexte
        events_text = "\n".join([
            f"- {e['title']}" 
            for e in events[:5]
        ])
        
        # Demander au LLM de choisir UNE catégorie large parmi la liste
        try:
            llm_prompt = f"""Tu es un assistant qui suggère des découvertes pour les gens.

Profil: {profile}
Ils cherchent actuellement: {events_text}

Pour "Osez la Nouveauté", choisis UNE catégorie LARGE parmi:
- Musique
- Sport
- Art
- Nature
- Spectacle
- Cuisine

RÈGLES:
1. La catégorie doit être DIFFÉRENTE de ce qu'ils demandent
2. Choisis une catégorie qui correspond PSYCHOLOGIQUEMENT à leur profil
3. Explique le lien avec UNE PHRASE courte et simple

Exemples de bonnes raisons:
- Cinéphile + sport = "Beaucoup de films d'action/boxe, pourquoi ne pas vivre la chose réelle ?"
- Fêtard + art = "Les galeries d'art ont souvent des vernissages festifs"
- Sportif + musique = "La musique live a la même énergie que le sport"
- Culturel + nature = "La nature est une galerie naturelle"

Réponds UNIQUEMENT avec ce format:
CATÉGORIE: [une seule]
RAISON: [une phrase simple]"""
            
            response = self.llm.invoke(llm_prompt)
            llm_text = response.content if hasattr(response, 'content') else str(response)
            
            print(f"[DEBUG LLM Novelty] Raw response:\n{llm_text}")
            
            # Parser la réponse
            category_suggestion = None
            reason = ""
            
            for line in llm_text.split('\n'):
                if line.startswith('CATÉGORIE:') or line.startswith('CATEGORIE:'):
                    category_suggestion = line.split(':', 1)[1].strip().lower()
                elif line.startswith('RAISON:'):
                    reason = line.split(':', 1)[1].strip()
            
            if not category_suggestion:
                category_suggestion = 'sport'  # Fallback
            
            print(f"[DEBUG] Osez la Nouveauté: {category_suggestion} -> {reason}")
            
            # Rechercher des événements dans cette catégorie LARGE
            _, _, formatted_events, _ = get_brussels_events_formatted_with_all(category_suggestion, limit=3)
            
            if formatted_events:
                # Choisir UN seul événement intelligemment
                best_event = formatted_events[0]
                
                result = f"\n\n🎲 **OSEZ LA NOUVEAUTÉ !**\n\n"
                result += f"💡 *{reason}*\n\n"
                result += f"1. **{best_event['title']}**\n"
                result += f"📅 {best_event['start_date']}\n"
                result += f"📍 {best_event['location']}\n"
                result += f"💰 {best_event['price']}\n"
                result += f"Description: {best_event['full_description']}\n"
                
                return result
        except Exception as e:
            print(f"[DEBUG] Erreur LLM Novelty: {e}")
            import traceback
            traceback.print_exc()
        
        return None

    def _add_ml_suggestions(self, content: str, system_instruction: str, category: str) -> str:
        """Ajoute les suggestions personnalisées ML en utilisant le LLM pour réfléchir"""
        # Détecter le profil
        profile = "Fêtard"
        for p in ['Fêtard', 'Culturel', 'Sportif', 'Cinéphile', 'Chill']:
            if p in system_instruction:
                profile = p
                break
        
        events = self.current_state.get("last_displayed_events", [])
        if not events:
            return content
        
        # Construire la liste des événements pour le LLM
        events_text = "\n".join([
            f"- {e['title']} ({e['location']}, {e['start_date']})" 
            for e in events[:8]
        ])
        
        # Demander au LLM de choisir et expliquer
        try:
            llm_prompt = f"""Tu es un assistant qui aide à choisir des activités.

Profil de l'utilisateur: {profile}
- Fêtard = aime les concerts, festivals, soirées, ambiance festive
- Culturel = aime les expos, musées, théâtre, galeries d'art
- Sportif = aime le sport, fitness, activités physiques
- Cinéphile = aime les films, projections, cinéma
- Chill = aime la nature, balades, détente

Voici les événements disponibles:
{events_text}

Choisis UN événement qui correspond le mieux au profil {profile} et explique pourquoi en UNE phrase.
Réponds UNIQUEMENT avec ce format:
ÉVÉNEMENT: [nom exact de l'événement]
RAISON: [ta phrase d'explication]"""
            
            response = self.llm.invoke(llm_prompt)
            llm_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parser la réponse
            chosen_event = None
            reason = ""
            
            for line in llm_text.split('\n'):
                if line.startswith('ÉVÉNEMENT:') or line.startswith('EVENEMENT:'):
                    event_name = line.split(':', 1)[1].strip()
                    # Trouver l'événement correspondant
                    for e in events:
                        if event_name.lower() in e['title'].lower() or e['title'].lower() in event_name.lower():
                            chosen_event = e
                            break
                elif line.startswith('RAISON:'):
                    reason = line.split(':', 1)[1].strip()
            
            # Si pas trouvé, prendre le premier
            if not chosen_event:
                chosen_event = events[0]
                reason = f"C'est un bon choix pour un {profile} !"
            
            content += f"\n\n🤖 **SUGGESTION PERSONNALISÉE ({profile})**\n\n"
            content += f"💡 *{reason}*\n\n"
            content += f"1. **{chosen_event['title']}**\n"
            content += f"📅 {chosen_event['start_date']}\n"
            content += f"📍 {chosen_event['location']}\n"
            content += f"💰 {chosen_event['price']}\n"
            content += f"Description: {chosen_event['description']}\n"
            
        except Exception as e:
            print(f"[DEBUG] Erreur LLM suggestion: {e}")
            # Fallback: premier événement
            if events:
                content += f"\n\n🤖 **SUGGESTION PERSONNALISÉE ({profile})**\n\n"
                content += f"1. **{events[0]['title']}**\n"
                content += f"📅 {events[0]['start_date']}\n"
                content += f"📍 {events[0]['location']}\n"
                content += f"💰 {events[0]['price']}\n"
        
        # Ajouter "Osez la nouveauté" avec des événements opposés
        opposite_content = self._get_opposite_events(system_instruction, category)
        if opposite_content:
            content += opposite_content
        
        return content

    def _format_response_to_html(self, response: str, category_context: str = "General") -> str:
        """Formate la réponse en HTML avec cartes cliquables et boutons Like (VERSION CORRIGÉE)"""
        if not response:
            return "<p>...</p>"
        
        # Si déjà du HTML avec event-list
        if '<ul class="event-list">' in response:
            return '<div class="response-content">\n' + response + '\n</div>'
        
        # Si c'est JUSTE un menu de suggestions (pas de contenu d'événements)
        if 'suggestion-btn' in response and '**ACTIVITÉS' not in response and '📅' not in response:
            return '<div class="response-content">\n' + response + '\n</div>'
        
        # DEBUG DÉTAILLÉ
        print(f"\n[DEBUG FULL] ===== DÉBUT FORMAT HTML =====")
        print(f"Response length: {len(response)}")
        print(f"Newlines count: {response.count(chr(10))}")
        print(f"Has pagination button: {'pagination-btn' in response}")
        print(f"Has ACTIVITÉS: {'**ACTIVITÉS' in response}")
        print(f"First 300 chars: {repr(response[:300])}")
        
        cleaned = response.replace('```html', '').replace('```', '')
        
        # NORMALISATION IMPORTANTE: Forcer les sauts de ligne avant chaque emoji/info
        print(f"\n[DEBUG] Before normalization - newlines: {cleaned.count(chr(10))}")
        
        # Garder trace des substitutions
        patterns_to_normalize = [
            (r'\s+(\d+\.\s+\*\*)', r'\n\1', 'Event numbers'),
            (r'\s+📅', '\n📅', 'Dates'),
            (r'\s+📍', '\n📍', 'Locations'),
            (r'\s+💰', '\n💰', 'Prices'),
            (r'\s+🔗', '\n🔗', 'URLs'),
            (r'\s+Description:', '\nDescription:', 'Descriptions'),
            (r'\s+💬', '\n\n💬', 'Activity count'),
            (r'\s+🔄', '\n🔄', 'Pagination'),
            (r'\s+🤖', '\n\n🤖', 'ML suggestions'),
            (r'\s+🎲', '\n\n🎲', 'Novelty'),
            (r'\s+💡', '\n💡', 'Ideas'),
        ]
        
        for pattern, replacement, desc in patterns_to_normalize:
            before = cleaned.count('\n')
            cleaned = re.sub(pattern, replacement, cleaned)
            after = cleaned.count('\n')
            print(f"  {desc}: {before} → {after} newlines")
        
        html_parts = []
        lines = cleaned.split('\n')
        print(f"\n[DEBUG] After split: {len(lines)} lines")
        
        # Afficher les premières lignes pour debug
        for i, line in enumerate(lines[:5]):
            print(f"  Line {i}: {repr(line[:80])}")
        
        print(f"\n[DEBUG] Starting parse loop...")
        current_section = []
        in_list = False
        list_items = []
        current_hidden_info = []
        current_event_category = category_context
        
        for line in lines:
            line = line.strip()
            
            # Détection des tags de catégorie
            if '<!-- CATEGORY:' in line:
                try:
                    current_event_category = line.split('<!-- CATEGORY:')[1].split(' -->')[0]
                except:
                    pass
                continue
            
            # Titres de section (TOUS les emojis de catégorie)
            section_emojis = ['🎯', '📌', '🌟', '🤖', '🎲', '❌', '📭', '💬', '🔄', '🎬', '🎵', '🎨', '🏃', '🌳', '🍳', '🆓']
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
                
                # Styles spécifiques
                if line.startswith('🤖'):
                    html_parts.append(f'<h3 class="section-ml">{line}</h3>')
                elif line.startswith('🎲'):
                    html_parts.append(f'<h3 class="section-routine">{line}</h3>')
                elif line.startswith('🎯') or line.startswith('🎬') or line.startswith('🎵') or line.startswith('🎨') or line.startswith('🏃') or line.startswith('🌳'):
                    html_parts.append(f'<h2 class="section-title">{line}</h2>')
                elif line.startswith('❌') or line.startswith('📭'):
                    html_parts.append(f'<div class="alert-message">{line}</div>')
                else:
                    html_parts.append(f'<h3 class="section-subtitle">{line}</h3>')
                continue
            
            # Item Liste (1. **Nom**) - REGEX AMÉLIORÉ
            event_match = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', line) or re.match(r'^(\d+)\.\s+([A-Z].+)', line)
            if event_match:
                print(f"[DEBUG PARSE] Event trouvé: '{line[:50]}...'")  # DEBUG
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
                
                # Bouton Like avec catégorie
                like_btn = f'<button class="like-btn" data-event-title="{content.replace(chr(34), chr(39))}" data-category="{current_event_category}" onclick="toggleLike(event, this)">❤️</button>'
                
                list_items.append(f'<li class="event-item" onclick="toggleEvent(this)">{like_btn} {content}')
                in_list = True
                continue
            
            # Détails
            if in_list:
                if any(line.startswith(x) for x in ['📅', '📍', '💰', '🆓', '**📅', '**📍', '**💰']):
                    line_clean = line.replace('**', '')
                    list_items[-1] += f'<div class="event-detail">{line_clean}</div>'
                elif line.startswith('🔗') or line.startswith('**🔗'):
                    url = None
                    if 'http' in line:
                        found = re.search(r'(https?://[^\s\)]+)', line)
                        if found:
                            url = found.group(1)
                    
                    if url:
                        current_hidden_info.append(f'<div class="event-detail link"><a href="{url}" target="_blank">🔗 Voir le site officiel</a></div>')
                    else:
                        current_hidden_info.append('<div class="event-detail">🔗 Lien non disponible</div>')
                elif line.startswith('Description:') or line.startswith('📖'):
                    desc = line.replace('Description:', '').replace('📖', '').strip()
                    current_hidden_info.append(f'<div class="event-description">📝 {desc}</div>')
                elif line and not line.startswith('<!--'):
                    current_hidden_info.append(f'<div class="event-info">{line}</div>')
            elif line and not line.startswith('<!--'):
                current_section.append(line)
        
        # Fermetures finales
        if list_items:
            if current_hidden_info:
                list_items[-1] += f'<div class="more-info">{"".join(current_hidden_info)}</div>'
            list_items[-1] += '<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>'
            html_parts.append('<ul class="event-list">' + ''.join(list_items) + '</ul>')
        
        if current_section:
            html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')

        # DEBUG: Montrer le HTML généré
        final_html = '<div class="response-content">\n' + '\n'.join(html_parts) + '\n</div>'
        print(f"[DEBUG HTML] Final output contains {len(html_parts)} parts, event-list: {'event-list' in final_html}")
        
        return final_html

    def _inject_css(self):
        # CSS maintenant dans index.html - plus besoin d'injecter
        return ""
