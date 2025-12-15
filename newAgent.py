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
        self.tools = [
            Tool(
                name="Unified Events Fetcher",
                func=fetch_all_events,
                description="Fetch events from ALL sources (EventBrite, Brussels API, TicketMaster) at once. Input should be a generic category keyword like 'music', 'sport', 'art', 'theatre', 'cinema', 'family'."
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
            "� Prix\n"
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

    def _format_response_to_html(self, response: str) -> str:
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
                
                # Bouton Like (Simplifié pour NewAgent)
                like_btn = f'<button class="like-btn" onclick="toggleLike(event, this)">❤️</button>'
                
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
        raw_response = self.agent.run(input=user_input)
        return self._format_response_to_html(raw_response)

