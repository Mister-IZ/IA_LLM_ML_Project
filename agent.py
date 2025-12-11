import os
import re
from typing import List
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
# On garde tes outils tels quels car ils marchaient bien
from tools import get_eventbrite_events, get_ticketmaster_events, get_brussels_events

class SocialAgentLangChain:
    def __init__(self):
        self.llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0.2,
            mistral_api_key=os.getenv("MISTRAL_API_KEY")
        )
        
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            k=5
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
        return """Tu es un assistant social à Bruxelles. Ta mission est d'aider les gens à trouver des activités.

    RÈGLES IMPORTANTES :
    1. Si l'utilisateur veut discuter (Bonjour, Blague, Philosophie), réponds naturellement.
    2. Si l'utilisateur cherche une activité, utilise tes outils et réponds avec ce FORMAT STRICT :

    🎯 TITRE DE LA SECTION

    1. **Nom de l'événement**
    📅 Date
    📍 Lieu
    💰 Prix
    🔗 Lien
    Description de l'événement.(SANS INVENTER)

    [... Autres événements ...]

    [SI UNE INSTRUCTION ML EST PRÉSENTE, AJOUTE CES SECTIONS EN RESPECTANT LE MÊME FORMAT DE CARTE :]
    ───────────────
    🤖 SUGGESTION PERSONNALISÉE (Nom Profil)
    1. **Nom de l'événement suggéré (Tiré de la liste ci-dessus)**
    📅 Date
    📍 Lieu
    💰 Prix
    🔗 Lien
    Description : Explication de pourquoi ça matche le profil.

    🎲 OSEZ LA NOUVEAUTÉ ! Sortir de son cercle peut aussi faire du bien.
    1. **Nom de l'activité (Tiré de la liste ou suggestion générique)**
    📅 Date
    📍 Lieu
    💰 Prix
    🔗 Lien
    Description : Pourquoi ça change la routine.
    """

    def _setup_tools(self):
        def recherche_brussels(query: str) -> str:
            try: return get_brussels_events(query)
            except Exception as e: return f"Erreur Brussels: {e}"
        
        def recherche_ticketmaster(query: str) -> str:
            try:
                # Mapping intelligent pour aider l'API
                cat = 'Music'
                q = query.lower()
                if 'sport' in q: cat = 'Sports'
                elif 'art' in q or 'theatre' in q: cat = 'Arts'
                elif 'cinema' in q or 'film' in q: cat = 'Film'
                return get_ticketmaster_events(cat)
            except Exception as e: return f"Erreur TM: {e}"
        
        def recherche_eventbrite(query: str) -> str:
            try: return get_eventbrite_events()
            except Exception as e: return f"Erreur EB: {e}"

        return [
            Tool(name="BrusselsAPI", func=recherche_brussels, description="Pour événements locaux, culturels et gratuits à Bruxelles."),
            Tool(name="TicketmasterAPI", func=recherche_ticketmaster, description="Pour grands concerts et sports."),
            Tool(name="EventBriteAPI", func=recherche_eventbrite, description="Pour ateliers et social.")
        ]

    def reset_conversation(self):
        self.memory.clear()

    def chat(self, message_complexe: str) -> str:
        """Gère la logique : Nettoyage Message -> Clarification -> Recherche -> Réponse HTML"""
        
        # 1. Extraction User Message vs System Instruction
        user_message = message_complexe.split("[SYSTEM_HIDDEN_INSTRUCTION")[0].strip()
        system_instruction = ""
        if "[SYSTEM_HIDDEN_INSTRUCTION" in message_complexe:
            system_instruction = message_complexe.split("[SYSTEM_HIDDEN_INSTRUCTION")[1].replace("]", "")

        msg_lower = user_message.lower()

        # 2. Détection du Contexte (Pour le bouton Like plus tard)
        # On essaie de deviner la catégorie de la demande
        current_context_category = "General"
        if any(x in msg_lower for x in ['ciné', 'film', 'théâtre']): current_context_category = "Cinema"
        elif any(x in msg_lower for x in ['sport', 'match', 'course']): current_context_category = "Sport"
        elif any(x in msg_lower for x in ['musi', 'concert', 'chanson']): current_context_category = "Music"
        elif any(x in msg_lower for x in ['art', 'expo', 'musée']): current_context_category = "Art"
        elif any(x in msg_lower for x in ['natur', 'parc', 'balade']): current_context_category = "Nature"

        # 3. Est-ce une recherche ou une discussion ?
        search_keywords = ['activ', 'événe', 'sortie', 'cherch', 'veur', 'propos', 'trouv', 
                          'ciné', 'sport', 'musi', 'concert', 'expo', 'théâtre', 'faire', 'voir']
        is_search = any(kw in msg_lower for kw in search_keywords)

        # Si PAS de recherche -> Mode Discussion (Bonjour, Blague...)
        if not is_search:
            # On envoie juste le message user à l'agent, SANS l'instruction ML
            # Comme ça, il n'essaie pas de forcer une recommandation d'événement
            raw_response = self.agent.run(user_message)
            return self._format_response_to_html(raw_response, current_context_category)

        # 4. Désambiguïsation (Clarification)
        # Cinéma
        if 'cinéma' in msg_lower and not any(x in msg_lower for x in ['film', 'théâtre', 'salle']):
            return self._format_response_to_html("""🎯 PRÉCISONS... <div class="suggestion-container"><button class="suggestion-btn" data-text="Je cherche des films">🎬 Films</button><button class="suggestion-btn" data-text="Je cherche du théâtre">🎭 Théâtre</button></div>""", "Cinema")
        # Musique
        if any(x in msg_lower for x in ['musique', 'zic']) and not any(x in msg_lower for x in ['concert', 'jouer']):
            return self._format_response_to_html("""🎯 PRÉCISONS... <div class="suggestion-container"><button class="suggestion-btn" data-text="Voir un concert">🎵 Concert</button><button class="suggestion-btn" data-text="Jam session">🎸 Pratiquer</button></div>""", "Music")
        # Sport
        if 'sport' in msg_lower and not any(x in msg_lower for x in ['voir', 'match', 'faire', 'pratiquer']):
             return self._format_response_to_html("""🎯 PRÉCISONS... <div class="suggestion-container"><button class="suggestion-btn" data-text="Voir un match">🏟️ Voir un match</button><button class="suggestion-btn" data-text="Faire du sport">🏃 Faire du sport</button></div>""", "Sport")

        # 5. Recherche (Execution)
        results = []
        try: results.append(self.tools[0].func(user_message))
        except: pass
        try: results.append(self.tools[1].func(user_message))
        except: pass
        try: results.append(self.tools[2].func(user_message))
        except: pass
        
        content_found = "\n".join([r for r in results if "Aucun" not in r and "Erreur" not in r])
        
        # Si rien trouvé, on laisse l'agent gérer l'erreur
        if not content_found:
             return self._format_response_to_html(self.agent.run(user_message), current_context_category)

        # 6. Prompt Final avec ML
        final_prompt = f"""
        L'utilisateur demande : "{user_message}"
        
        Voici les événements trouvés (API) :
        {content_found}

        [INSTRUCTION ML : {system_instruction}]

        RÉPONSE ATTENDUE :
        1. Liste les résultats trouvés sous forme de cartes.
        2. SI INSTRUCTION ML : Ajoute les sections 🤖 SUGGESTION et 🎲 NOUVEAUTÉ.
           ⚠️ IMPORTANT : Dans ces sections spéciales, NE FAIS PAS DE PHRASES. 
           Recopie les détails de l'événement sous forme de carte (1. **Nom**...) pour que l'utilisateur puisse cliquer dessus
        """
                # RÉPONSE :
        # 1. Liste les résultats trouvés.
        # 2. SI tu as une instruction ML, ajoute les sections 🤖 SUGGESTION et 🎲 NOUVEAUTÉ à la fin.
        #    -> Pour la SUGGESTION, choisis UN VRAI événement de la liste ci-dessus qui correspond au profil.

        response = self.agent.run(final_prompt)
        return self._format_response_to_html(response, current_context_category)

    def _format_response_to_html(self, response: str, category_context: str = "General") -> str:
        """Formate la réponse en HTML, gère les liens et injecte le bouton Like avec Catégorie"""
        if not response: return "<p>...</p>"
        
        # Si c'est juste nos boutons de clarification
        if 'suggestion-btn' in response:
             return self._inject_css() + '\n<div class="response-content">\n' + response + '\n</div>'

        cleaned = response.replace('```html', '').replace('```', '')
        
        html_parts = []
        lines = cleaned.split('\n')
        current_section = []
        in_list = False
        list_items = []
        current_hidden_info = [] 
        
        for line in lines:
            line = line.strip()
            
            # Gestion des titres (Sections)
            if any(line.startswith(x) for x in ['🎯', '📌', '🌟', '🤖', '🎲']):
                # Fermeture liste précédente
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
                if line.startswith('🤖'): html_parts.append(f'<h3 class="section-ml">{line}</h3>')
                elif line.startswith('🎲'): html_parts.append(f'<h3 class="section-routine">{line}</h3>')
                elif line.startswith('🎯'): html_parts.append(f'<h2 class="section-title">{line}</h2>')
                else: html_parts.append(f'<h3 class="section-subtitle">{line}</h3>')
                continue
            
            # Détection Item Liste (1. **Nom**)
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
                
                # --- CRUCIAL : BOUTON LIKE AVEC CATÉGORIE ---
                # On injecte 'category_context' dans le onclick pour que le JS l'envoie au serveur
                like_btn = f'<button class="like-btn" onclick="toggleLike(this, \'{content.replace("'", "\\'")}\', \'{category_context}\')">❤️</button>'
                
                list_items.append(f'<li class="event-item" onclick="toggleEvent(this)">{like_btn} {content}')
                in_list = True
                continue
            
            # Détails (Date, Lieu, etc.)
            if in_list:
                if any(line.startswith(x) for x in ['📅', '📍', '💰', '🆓']):
                    list_items[-1] += f'<div class="event-detail">{line}</div>'
                elif line.startswith('🔗'):
                    # Correction URL
                    url = "https://www.google.com"
                    if 'http' in line:
                        found = re.search(r'(https?://[^\s\)]+)', line)
                        if found: url = found.group(1)
                    line = f'<a href="{url}" target="_blank">Voir le site officiel</a>'
                    current_hidden_info.append(f'<div class="event-detail link">{line}</div>')
                elif line:
                    current_hidden_info.append(f'<div class="event-description">{line}</div>')
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

        return self._inject_css() + '\n<div class="response-content">\n' + '\n'.join(html_parts) + '\n</div>'

    def _inject_css(self):
        return """
        <style>
        .event-list { list-style: none; padding: 0; margin: 20px 0; }
        .event-item { background: white; border-left: 4px solid #007bff; padding: 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); cursor: pointer; transition: all 0.2s; }
        .event-item:hover { transform: translateY(-2px); background-color: #f8f9fa; }
        .event-item strong { color: #2c3e50; font-size: 1.1em; display: block; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        .event-detail { margin: 5px 0; padding-left: 25px; color: #555; }
        .more-info { display: none; margin-top: 15px; padding-top: 15px; border-top: 1px dashed #ddd; }
        .event-item.active .more-info { display: block; }
        .click-hint { font-size: 0.8em; color: #999; text-align: center; margin-top: 10px; text-transform: uppercase; }
        .event-item.active .click-hint { display: none; }
        
        .section-title { color: #2c3e50; margin: 30px 0 15px 0; border-bottom: 2px solid #007bff; font-size: 1.4em; }
        .section-ml { color: #6c5ce7; margin: 25px 0 12px 0; background: rgba(108, 92, 231, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #6c5ce7; }
        .section-routine { color: #e17055; margin: 25px 0 12px 0; background: rgba(225, 112, 85, 0.1); padding: 10px; border-radius: 5px; border-left: 4px solid #e17055; }
        
        .like-btn { float: right; background: none; border: 1px solid #ddd; border-radius: 50%; cursor: pointer; font-size: 1.2em; padding: 5px; z-index: 10; position: relative; }
        .like-btn:hover { transform: scale(1.2); background-color: #ffe6e6; }
        .like-btn.liked { background-color: #ff4757; border-color: #ff4757; }
        
        .suggestion-container { display: flex; gap: 10px; margin-top: 15px; }
        .suggestion-btn { background: white; border: 1px solid #007bff; color: #007bff; padding: 8px 16px; border-radius: 20px; cursor: pointer; }
        .suggestion-btn:hover { background: #007bff; color: white; }
        </style>
        """