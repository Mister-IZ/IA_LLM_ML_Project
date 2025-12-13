import os
import re
from typing import List, Dict, Optional, Tuple
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage

# Import des nouvelles fonctions optimisées
from tools_new import (
    get_brussels_events_formatted, 
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
            "all_events": [],
            "last_displayed_events": [],
            "last_ml_category": "General"
        }
        self.memory.clear()

    def _is_pagination_request(self, message: str) -> bool:
        """Détecte si c'est une demande de pagination"""
        return message.lower().strip() in ['autre', 'autres', 'suivant', 'encore', 'plus', 'next']

    def _is_specific_event_request(self, message: str) -> Tuple[bool, Optional[int]]:
        """Détecte si c'est une demande spécifique sur un événement (ex: "3", "détails sur 5")"""
        message_lower = message.lower().strip()
        
        # Numéro simple
        if message_lower.isdigit():
            return True, int(message_lower)
        
        # Patterns comme "plus d'infos sur 5", "détails 3"
        patterns = [
            r'(\d+)(?:\s|$)',
            r'sur\s+(\d+)',
            r'num[ée]ro\s+(\d+)',
            r'[ée]v[ée]nement\s+(\d+)',
            r'd[ée]tails?\s+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                return True, int(match.group(1))
        
        return False, None

    def _get_event_details(self, event_number: int) -> str:
        """Récupère les détails complets d'un événement spécifique"""
        events = self.current_state["last_displayed_events"]
        
        if not events:
            return "❌ Aucun événement récent. Fais d'abord une recherche !"
        
        if event_number < 1 or event_number > len(events):
            return f"❌ Numéro invalide. Choisis entre 1 et {len(events)}."
        
        event = events[event_number - 1]
        
        result = f"🎯 **DÉTAILS COMPLETS - {event['title']}**\n\n"
        result += f"**📍 Lieu :** {event['location']}\n"
        result += f"**📅 Date :** {event['start_date']}\n"
        result += f"**💰 Prix :** {event['price']}\n"
        if event.get('url'):
            result += f"**🔗 Lien :** {event['url']}\n"
        result += f"\n**📖 Description complète :**\n{event.get('full_description', event['description'])}\n\n"
        
        # Conseils sociaux contextuels
        title_lower = event['title'].lower()
        if any(word in title_lower for word in ['atelier', 'workshop']):
            result += "💡 **Conseil :** Les ateliers sont parfaits pour rencontrer des gens !\n"
        elif any(word in title_lower for word in ['concert', 'festival']):
            result += "💡 **Conseil :** Ambiance conviviale garantie !\n"
        elif any(word in title_lower for word in ['film', 'cinéma', 'projection']):
            result += "💡 **Conseil :** Les projections sont souvent suivies de discussions !\n"
        
        result += f"\n🔙 Dis 'retour' pour revenir à la liste"
        
        return self._format_response_to_html(result, self.current_state["last_ml_category"])

    def _handle_pagination(self) -> str:
        """Gère la pagination des résultats"""
        self.current_state["current_page"] += 1
        page = self.current_state["current_page"]
        filter_type = self.current_state["filter_type"]
        
        # Recharger avec la nouvelle page
        api = get_brussels_api()
        
        # Déterminer le keyword de recherche
        keyword = None
        if filter_type and filter_type in EventFilter.FILTER_MAP:
            keywords = EventFilter.FILTER_MAP[filter_type].get('keywords', [])
            if keywords:
                keyword = keywords[0]
        
        # Rechercher la page suivante
        result_text, ml_category, formatted_events = get_brussels_events_formatted(
            keyword or "bruxelles", 
            page=page, 
            limit=8
        )
        
        if not formatted_events:
            self.current_state["current_page"] = 1
            return self._format_response_to_html(
                "📭 **Plus d'activités de ce type.**\n\n🎯 Essaie une autre catégorie !",
                ml_category
            )
        
        self.current_state["last_displayed_events"] = formatted_events
        
        return self._format_response_to_html(result_text, ml_category)

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
        
        # 3. Gestion des demandes spécifiques (numéro d'événement)
        is_specific, event_number = self._is_specific_event_request(user_message)
        if is_specific and event_number:
            return self._get_event_details(event_number)
        
        # 4. Gestion de la pagination
        if self._is_pagination_request(user_message):
            return self._handle_pagination()
        
        # 5. Gestion du retour à la liste
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
        
        # Toujours essayer Brussels d'abord
        try:
            result_text, ml_category, formatted_events = get_brussels_events_formatted(user_message)
            if formatted_events:
                results.append(result_text)
                self.current_state["last_displayed_events"] = formatted_events
                self.current_state["last_ml_category"] = ml_category
                current_context_category = ml_category
        except Exception as e:
            print(f"[DEBUG] Erreur Brussels: {e}")
        
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

    def _add_ml_suggestions(self, content: str, system_instruction: str, category: str) -> str:
        """Ajoute les suggestions personnalisées ML"""
        # Détecter le profil
        profile = "Fêtard"
        for p in ['Fêtard', 'Culturel', 'Sportif', 'Cinéphile', 'Chill']:
            if p in system_instruction:
                profile = p
                break
        
        # Suggestion personnalisée basée sur le premier événement
        if self.current_state["last_displayed_events"]:
            first_event = self.current_state["last_displayed_events"][0]
            content += f"\n\n🤖 **SUGGESTION PERSONNALISÉE ({profile})**\n\n"
            content += f"1. **{first_event['title']}**\n"
            content += f"📅 {first_event['start_date']}\n"
            content += f"📍 {first_event['location']}\n"
            content += f"💰 {first_event['price']}\n"
            content += f"Description: {first_event['description']} Parfait pour un {profile} !\n"
        
        return content

    def _format_response_to_html(self, response: str, category_context: str = "General") -> str:
        """Formate la réponse en HTML avec cartes cliquables et boutons Like"""
        if not response:
            return "<p>...</p>"
        
        # Si c'est juste nos boutons
        if 'suggestion-btn' in response:
            return self._inject_css() + '\n<div class="response-content">\n' + response + '\n</div>'
        
        cleaned = response.replace('```html', '').replace('```', '')
        
        # Normalisation: "/" → multi-ligne
        cleaned = re.sub(r'\s*/\s*📅', '\n📅', cleaned)
        cleaned = re.sub(r'\s*/\s*📍', '\n📍', cleaned)
        cleaned = re.sub(r'\s*/\s*💰', '\n💰', cleaned)
        cleaned = re.sub(r'\s*/\s*🔗', '\n🔗', cleaned)
        cleaned = re.sub(r'\s*/\s*Description:', '\nDescription:', cleaned)
        
        html_parts = []
        lines = cleaned.split('\n')
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
            
            # Titres de section
            if any(line.startswith(x) for x in ['🎯', '📌', '🌟', '🤖', '🎲', '❌', '📭', '💬', '🔄']):
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
                elif line.startswith('🎯'):
                    html_parts.append(f'<h2 class="section-title">{line}</h2>')
                elif line.startswith('❌') or line.startswith('📭'):
                    html_parts.append(f'<div class="alert-message">{line}</div>')
                else:
                    html_parts.append(f'<h3 class="section-subtitle">{line}</h3>')
                continue
            
            # Item Liste (1. **Nom**)
            if re.match(r'^\d+\.\s+\*\*', line) or re.match(r'^\d+\.\s+[A-Z]', line):
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

        return self._inject_css() + '\n<div class="response-content">\n' + '\n'.join(html_parts) + '\n</div>'

    def _inject_css(self):
        return """
        <style>
        .event-list { list-style: none; padding: 0; margin: 20px 0; }
        .event-item { background: white; border-left: 4px solid #007bff; padding: 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); cursor: pointer; transition: all 0.2s; }
        .event-item:hover { transform: translateY(-2px); background-color: #f8f9fa; }
        .event-item strong { color: #2c3e50; font-size: 1.1em; display: block; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        .event-detail { margin: 5px 0; padding-left: 25px; color: #555; }
        .event-description { margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; color: #333; }
        .more-info { display: none; margin-top: 15px; padding-top: 15px; border-top: 1px dashed #ddd; }
        .event-item.active .more-info { display: block; }
        .click-hint { font-size: 0.8em; color: #999; text-align: center; margin-top: 10px; }
        .event-item.active .click-hint { display: none; }
        
        .section-title { color: #2c3e50; margin: 30px 0 15px 0; border-bottom: 2px solid #007bff; font-size: 1.4em; }
        .section-ml { color: #6c5ce7; margin: 25px 0 12px 0; background: rgba(108, 92, 231, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #6c5ce7; }
        .section-routine { color: #e17055; margin: 25px 0 12px 0; background: rgba(225, 112, 85, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #e17055; }
        .alert-message { background: #fff3cd; padding: 15px; border-radius: 8px; margin: 10px 0; }
        
        .like-btn { float: right; background: none; border: 1px solid #ddd; border-radius: 50%; cursor: pointer; font-size: 1.2em; padding: 5px; z-index: 10; position: relative; }
        .like-btn:hover { transform: scale(1.2); background-color: #ffe6e6; }
        .like-btn.liked { background-color: #ff4757; border-color: #ff4757; }
        
        .section { margin: 10px 0; line-height: 1.6; }
        .event-info { padding: 5px 0; color: #666; }
        </style>
        """
