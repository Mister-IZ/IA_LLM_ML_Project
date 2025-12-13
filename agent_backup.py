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
    Description: [RECOPIE EXACTEMENT la description retournée par le tool]

    ⚠️ RÈGLES CRUCIALES POUR LES DÉTAILS :
    - RECOPIE MOT POUR MOT le Prix retourné par le tool (ex: "🆓 Gratuit", "25 EUR", "Non communiqué")
    - RECOPIE MOT POUR MOT la Description retournée par le tool
    - Si un champ est absent dans la réponse du tool, écris "Non communiqué" au lieu de rien
    - NE PAS inventer, résumer ou reformuler les informations
    - GARDE TOUJOURS le préfixe "Description:" suivi du texte exact

    [... Autres événements ...]

    [SI UNE INSTRUCTION ML EST PRÉSENTE, AJOUTE CES SECTIONS EN RESPECTANT LE MÊME FORMAT DE CARTE :]
    ───────────────
    
    SECTION 1 - Titre exact à écrire :
    🤖 SUGGESTION PERSONNALISÉE (Nom_Du_Profil)
    
    Ensuite une ligne vide, puis EXACTEMENT ce format :
    1. **Nom de l'événement suggéré**
    📅 [Date]
    📍 [Lieu]
    💰 [Prix]
    🔗 [Lien]
    Description: [Description originale]. Parfait pour un [Profil] car [1 phrase].

    SECTION 2 - Titre exact à écrire :
    🎲 OSEZ LA NOUVEAUTÉ !
    
    Ensuite une ligne vide, puis EXACTEMENT ce format :
    1. **Nom de l'événement opposé**
    📅 [Date]
    📍 [Lieu]
    💰 [Prix]
    🔗 [Lien]
    Description: [Description originale]. Sortir de sa zone de confort avec [1 phrase].
    
    ⚠️ RÈGLES ABSOLUES POUR LES SECTIONS ML :
    - CHAQUE ligne DOIT commencer par un emoji ou le numéro 1.
    - PAS DE texte sur une seule ligne. OBLIGATOIREMENT sur plusieurs lignes.
    - Tu DOIS choisir des événements DE LA LISTE FOURNIE. PAS d'événement extérieur.
    - Si un événement de la liste n'a pas d'information, utilise "Non communiqué".
    - Les cartes doivent être IDENTIQUES aux autres (même format exact).
    """

    def _setup_tools(self):
        def recherche_brussels(query: str) -> str:
            try: return get_brussels_events(query)
            except Exception as e: return f"Erreur Brussels: {e}"
        
        def recherche_ticketmaster(query: str) -> str:
            try:
                # Mapping intelligent : catégorie générale SEULEMENT, pas de genres précis
                cat = 'Music'  # Par défaut
                q = query.lower()
                
                if 'sport' in q: 
                    cat = 'Sports'
                elif 'art' in q or 'theatre' in q or 'spectacle' in q: 
                    cat = 'Arts & Theatre'
                elif 'cinema' in q or 'film' in q: 
                    cat = 'Film'
                else:
                    cat = 'Music'  # Par défaut concerts/musique
                
                # PAS de genre_filter : on laisse Ticketmaster retourner tout ce qui correspond à la catégorie
                return get_ticketmaster_events(cat, genre_filter=None)
            except Exception as e: return f"Erreur TM: {e}"
        
        def recherche_eventbrite(query: str) -> str:
            try: return get_eventbrite_events()
            except Exception as e: return f"Erreur EB: {e}"

        return [
            Tool(name="BrusselsAPI", func=recherche_brussels, description="Pour événements locaux, culturels et gratuits à Bruxelles."),
            Tool(name="TicketmasterAPI", func=recherche_ticketmaster, description="Pour grands concerts et sports."),
            Tool(name="EventBriteAPI", func=recherche_eventbrite, description="Pour ateliers et social.")
        ]

    def _get_opposite_events(self, system_instruction: str, current_category: str) -> str:
        """Recherche des événements dans une catégorie opposée au profil de l'utilisateur"""
        
        # Mapping des profils vers leurs catégories opposées (inclut Nature!)
        opposite_map = {
            'Fêtard': ['nature', 'expositions', 'théâtre'],  # Fêtard -> propose nature/calme
            'Culturel': ['sports', 'nature', 'concerts'],  # Culturel -> propose sport/nature
            'Sportif': ['expositions', 'théâtre', 'nature'],  # Sportif -> propose culture/nature
            'Cinéphile': ['sports', 'nature', 'concerts'],  # Cinéphile -> propose sport/nature
            'Chill': ['concerts', 'sports', 'expositions']  # Chill -> propose dynamique
        }
        
        # Détection du profil dans l'instruction
        profile = "Fêtard"  # Par défaut
        for prof in opposite_map.keys():
            if prof in system_instruction:
                profile = prof
                break
        
        # Éviter de rechercher dans la catégorie actuelle
        opposite_categories = opposite_map.get(profile, ['art', 'expositions'])
        
        # Filtrer pour ne pas rechercher dans la catégorie actuelle
        if current_category == "Music":
            opposite_categories = [c for c in opposite_categories if c not in ['concerts', 'musique']]
        elif current_category == "Art":
            opposite_categories = [c for c in opposite_categories if c not in ['art', 'expositions', 'théâtre']]
        elif current_category == "Sport":
            opposite_categories = [c for c in opposite_categories if c not in ['sports']]
        elif current_category == "Cinema":
            # Si on cherche des films, éviter le cinéma et proposer autre chose
            opposite_categories = [c for c in opposite_categories if c not in ['film', 'cinéma', 'ciné']]
        
        # Si pas de catégorie opposée disponible, prendre la première par défaut
        if not opposite_categories:
            opposite_categories = ['expositions']
        
        # Rechercher dans la première catégorie opposée
        query = opposite_categories[0]
        
        # Si on cherche 'nature', utiliser des mots-clés spécifiques Brussels
        if query == 'nature':
            query = 'parc balade jardin'  # Mots-clés qui trouvent des events nature sur Brussels
        
        print(f"[DEBUG] Recherche opposée pour profil '{profile}' en catégorie '{current_category}' -> Query: '{query}'")
        
        try:
            # Essayer Brussels API en priorité (plus de variété)
            result = self.tools[0].func(query)
            print(f"[DEBUG] Brussels API result for '{query}': {len(result) if result else 0} chars")
            if result and "Aucun" not in result and "Erreur" not in result:
                # Limiter à 3 événements pour ne pas surcharger
                lines = result.split('\n')
                limited_result = []
                event_count = 0
                for line in lines:
                    if line.strip().startswith(tuple([f"{i}." for i in range(1, 20)])):
                        event_count += 1
                        if event_count > 3:
                            break
                    limited_result.append(line)
                final_result = '\n'.join(limited_result)
                print(f"[DEBUG] Returning {event_count} opposite events from Brussels")
                return final_result
            
            # Fallback sur Ticketmaster si Brussels ne retourne rien
            if query in ['sports', 'sport']:
                cat = 'Sports'
            elif query in ['concerts', 'musique']:
                cat = 'Music'
            else:
                cat = 'Arts'
            
            result = self.tools[1].func(cat)
            if result and "Aucun" not in result:
                # Limiter à 3 événements
                lines = result.split('\n')
                limited_result = []
                event_count = 0
                for line in lines:
                    if line.strip().startswith(tuple([f"{i}." for i in range(1, 20)])):
                        event_count += 1
                        if event_count > 3:
                            break
                    limited_result.append(line)
                return '\n'.join(limited_result)
                
        except Exception as e:
            print(f"[DEBUG] Erreur recherche opposée: {e}")
        
        # IMPORTANT: Retourner None si rien trouvé (pas "") pour éviter que l'agent invente
        print(f"[DEBUG] Aucun événement opposé trouvé, retour None")
        return None  # None = pas de section "Osez la nouveauté"

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

        # 5. Recherche (Execution) - Intelligente selon la demande
        results = []
        
        # Toujours essayer Brussels d'abord (événements locaux)
        try: 
            result_brussels = self.tools[0].func(user_message)
            if result_brussels and "Aucun" not in result_brussels and "Erreur" not in result_brussels:
                results.append(result_brussels)
        except: pass
        
        # Déterminer si on doit appeler Ticketmaster/EventBrite
        should_call_ticketmaster = True
        should_call_eventbrite = True
        
        # Si demande spécifique expo/musée/art → NE PAS appeler Ticketmaster (concerts/sports)
        if any(x in msg_lower for x in ['expo', 'musée', 'musee', 'galerie', 'art', 'peinture']):
            should_call_ticketmaster = False
        
        # Si demande spécifique concert/musique → Appeler Ticketmaster
        if any(x in msg_lower for x in ['concert', 'musique', 'music', 'live', 'band']):
            should_call_ticketmaster = True
            should_call_eventbrite = False
        
        # Si demande sport → Ticketmaster Sports
        if any(x in msg_lower for x in ['sport', 'match', 'foot', 'basket']):
            should_call_ticketmaster = True
            should_call_eventbrite = False
        
        # Appel conditionnel Ticketmaster
        if should_call_ticketmaster:
            try: 
                result_ticketmaster = self.tools[1].func(user_message)
                if result_ticketmaster and "Aucun" not in result_ticketmaster:
                    results.append(result_ticketmaster)
            except: pass
        
        # Appel conditionnel EventBrite
        if should_call_eventbrite:
            try: 
                result_eventbrite = self.tools[2].func(user_message)
                if result_eventbrite and "Aucun" not in result_eventbrite:
                    results.append(result_eventbrite)
            except: pass
        
        content_found = "\n".join([r for r in results if "Aucun" not in r and "Erreur" not in r])
        
        # Si rien trouvé → Message clair au lieu de laisser l'agent chercher ailleurs
        if not content_found:
            # Message spécifique selon le type de demande
            if any(x in msg_lower for x in ['expo', 'musée', 'musee', 'galerie', 'art']):
                no_result_msg = """
🎨 **Aucune exposition ou visite culturelle disponible en ce moment**

Je n'ai pas trouvé d'expositions, musées ou galeries sur Brussels Agenda actuellement.

💡 **Suggestions :**
- Essaie de revenir plus tard, de nouvelles expos sont ajoutées régulièrement
- Tu peux me demander d'autres types d'activités : théâtre, concerts, spectacles, sport...
- Ou visite directement les sites des musées bruxellois : Bozar, MIMA, Wiels, Atomium...
"""
                return self._format_response_to_html(no_result_msg, current_context_category)
            else:
                return self._format_response_to_html(self.agent.run(user_message), current_context_category)

        # 6. Recherche d'événements opposés pour "Osez la nouveauté"
        opposite_events = None
        if system_instruction:  # Si on a une instruction ML (donc un profil)
            opposite_events = self._get_opposite_events(system_instruction, current_context_category)
            if opposite_events:
                print(f"[DEBUG] Opposite events found: {len(opposite_events)} chars")
                print(f"[DEBUG] First 200 chars: {opposite_events[:200]}")
            else:
                print(f"[DEBUG] Aucun événement opposé trouvé - section 'Osez la nouveauté' sera omise")
        
        # Construire la section "Osez la nouveauté" SEULEMENT si on a des événements
        osez_section = ""
        osez_instruction = ""
        if opposite_events:
            osez_section = f"\nLISTE DES ÉVÉNEMENTS POUR 'OSEZ LA NOUVEAUTÉ' (catégorie opposée) :\n{opposite_events}\n"
            osez_instruction = """
🎲 OSEZ LA NOUVEAUTÉ !

1. **Nom** (DOIT être un événement de la LISTE ci-dessus)
📅 Date
📍 Lieu
💰 Prix
🔗 Lien
Description: Texte. Sortir de sa zone de confort avec [1 phrase].
"""
        
        # 7. Prompt Final avec ML
        final_prompt = f"""
L'utilisateur demande : "{user_message}"

LISTE DES ÉVÉNEMENTS DISPONIBLES :
{content_found}
{osez_section}
[INSTRUCTION ML : {system_instruction}]

RÉPONSE OBLIGATOIRE - FORMAT EXACT (CHAQUE DÉTAIL SUR SA PROPRE LIGNE) :

Pour chaque événement, tu DOIS utiliser ce format avec un retour à la ligne après chaque détail :
1. **Nom de l'événement**
📅 Date
📍 Lieu  
💰 Prix
🔗 Lien
Description: Texte

⚠️ CRUCIAL : NE PAS mettre tout sur une seule ligne avec des "/". CHAQUE emoji doit être sur sa PROPRE ligne.

SI instruction ML présente, ajoute ces 2 sections à la fin :

🤖 SUGGESTION PERSONNALISÉE (Nom_Du_Profil)

1. **Nom**
📅 Date
📍 Lieu
💰 Prix
🔗 Lien
Description: Texte. Parfait pour un [Profil] car [1 phrase].
{osez_instruction}
⚠️ RÈGLES ABSOLUES :
- Format MULTI-LIGNE obligatoire (pas de "/" entre les détails)
- RECOPIE les infos exactes sans inventer
- Choisis UNIQUEMENT des événements de la LISTE fournie
- Si pas de liste "OSEZ LA NOUVEAUTÉ" fournie, NE PAS ajouter cette section
"""

        response = self.agent.run(final_prompt)
        return self._format_response_to_html(response, current_context_category)

    def _format_response_to_html(self, response: str, category_context: str = "General") -> str:
        """Formate la réponse en HTML, gère les liens et injecte le bouton Like avec Catégorie"""
        if not response: return "<p>...</p>"
        
        # Si c'est juste nos boutons de clarification
        if 'suggestion-btn' in response:
             return self._inject_css() + '\n<div class="response-content">\n' + response + '\n</div>'

        cleaned = response.replace('```html', '').replace('```', '')
        
        # --- NORMALISATION : Convertir format compact "/" en multi-ligne ---
        # L'agent retourne parfois "1. **Nom** / 📅 Date / 📍 Lieu / ..." au lieu de multi-ligne
        # On convertit ça en format multi-ligne pour que le parser fonctionne
        import re
        # Pattern pour détecter le format compact et le convertir
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
        current_event_category = category_context  # Catégorie courante de l'événement
        
        for line in lines:
            line = line.strip()
            
            # --- DÉTECTION DES TAGS DE CATÉGORIE ---
            # Cherche les commentaires HTML <!-- CATEGORY:Art --> pour tracker la catégorie
            if '<!-- CATEGORY:' in line:
                try:
                    current_event_category = line.split('<!-- CATEGORY:')[1].split(' -->')[0]
                except:
                    pass
                continue  # Ne pas afficher le commentaire
            
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
                
                # --- CRUCIAL : BOUTON LIKE AVEC CATÉGORIE DE L'ÉVÉNEMENT ---
                # On utilise la catégorie détectée depuis les tags HTML, pas la catégorie de recherche globale
                like_btn = f'<button class="like-btn" data-event-title="{content.replace(chr(34), chr(92)+chr(34))}" data-category="{current_event_category}" onclick="toggleLike(event, this)">❤️</button>'
                
                list_items.append(f'<li class="event-item" onclick="toggleEvent(this)">{like_btn} {content}')
                in_list = True
                continue
            
            # Détails (Date, Lieu, etc.)
            if in_list:
                if any(line.startswith(x) for x in ['📅', '📍', '💰', '🆓']):
                    list_items[-1] += f'<div class="event-detail">{line}</div>'
                elif line.startswith('🔗'):
                    # Extraction URL
                    url = None
                    if 'http' in line:
                        found = re.search(r'(https?://[^\s\)]+)', line)
                        if found: url = found.group(1)
                    
                    if url:
                        line = f'<a href="{url}" target="_blank">Voir le site officiel</a>'
                        current_hidden_info.append(f'<div class="event-detail link">{line}</div>')
                    else:
                        # Si pas d'URL, on n'affiche rien (ou on peut afficher "Lien non disponible")
                        current_hidden_info.append(f'<div class="event-detail">🔗 Lien non disponible</div>')
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