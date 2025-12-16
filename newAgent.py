import os
import re
import random
from typing import List, Dict, Optional, Tuple
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage

from toolsFolder.eventBriteTool import (get_eventBrite_events, fetch_events_to_cache)
from toolsFolder.eventBrusselsTool import get_brussels_events
from toolsFolder.ticketMasterTool import get_ticketmaster_events

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
    
    # VALIDATION: Check if category is valid
    if cat_lower not in mapping:
        valid_categories = list(mapping.keys())
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
                description="Fetch events from ALL sources (EventBrite, Brussels API, TicketMaster) at once. Input should be a generic category keyword like 'music', 'sport', 'art', 'theatre', 'cinema', 'family', 'nature'."
            )
        ]

        self.system_prompt = (
            "You are an event recommendation assistant. IMPORTANT: You MUST reformat all raw event data.\n\n"
            "WORKFLOW:\n"
            "1. Use the 'Unified Events Fetcher' tool to find events (returns raw data from multiple sources)\n"
            "2. Parse the raw results and SELECT the best 5 events\n"
            "3. REFORMAT EACH EVENT to the exact format below (do not keep raw format!)\n"
            "4. Return ONLY reformatted events, never raw text\n"
            "\n"
            "**SÉLECTION DES ÉVÉNEMENTS :**\n"
            "- EXACTEMENT 5 événements seulement\n"
            "- Diversifie : 2 Brussels API + 2 Ticketmaster + 1 EventBrite\n"
            "- Choisis les plus pertinents et intéressants\n"
            "- Si moins de 5 disponibles, affiche seulement ceux-là\n"
            "\n\n"
            "**FORMAT OBLIGATOIRE - ABSOLUMENT À RESPECTER :**\n"
            "Chaque événement DOIT avoir EXACTEMENT ce format (sinon parsing HTML échoue):\n"
            "\n"
            "1. **Nom de l'événement**\n"
            "📅 Date (ex: 16 décembre 2025)\n"
            "📍 Lieu (ex: Palais des Beaux-Arts - Bozar)\n"
            "💰 Prix (ou 'Gratuit' ou 'Prix non précisé')\n"
            "🔗 https://[URL-COMPLÈTE-ICI]\n"
            "Description: [Texte exact et complet de la description]\n"
            "\n"
            "**RÈGLES STRICTES DE FORMATAGE :**\n"
            "✓ CHAQUE emoji sur sa PROPRE LIGNE UNIQUE\n"
            "✓ JAMAIS deux infos sur la même ligne\n"
            "✓ JAMAIS le format: '📅 Date - 📍 Lieu' (INTERDIT!)\n"
            "✓ JAMAIS le format: 'Titre - Date au Lieu' (INTERDIT!)\n"
            "✓ L'URL après 🔗 DOIT être complète (http:// ou https://)\n"
            "✓ Une ligne vide entre chaque événement\n"
            "✓ Description sur UNE SEULE LIGNE (pas de retour à la ligne)\n"
            "\n"
            "**✓ BON FORMAT :**\n"
            "1. **L'inconnu de la grande arche**\n"
            "📅 16-20 décembre 2025\n"
            "📍 Cinéma Aventure\n"
            "💰 Prix non précisé\n"
            "🔗 https://example.com/film1\n"
            "Description: Un film sur la construction de la Grande Arche de la Défense.\n"
            "\n"
            "**✗ MAUVAIS FORMAT (À ÉVITER!) :**\n"
            "L'inconnu de la grande arche - Du 16 au 20 décembre 2025 au Cinéma Aventure. Un film sur...\n"
            "(Pourquoi c'est mauvais: tout sur une ligne, pas parsable!)\n"
        )


        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            system_message=SystemMessage(content=self.system_prompt)
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
        return "Curieux"  # Défaut

    def _extract_profile_tag(self, user_message: str) -> Tuple[str, str]:
        """Extrait un tag [PROFILE:XXX] au début du message s'il existe."""
        profile = None
        cleaned = user_message
        match = re.match(r"\[PROFILE:([^\]]+)\]\s*(.*)", user_message, flags=re.IGNORECASE)
        if match:
            profile = match.group(1).strip()
            cleaned = match.group(2).strip()
        return profile, cleaned

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

    def _generate_ml_suggestion(self, current_results: str, profile: str) -> str:
        """
        Génère une suggestion personnalisée en cherchant le MEILLEUR événement
        parmi les résultats actuels trouvés par l'agent.
        """
        if not current_results or len(current_results) < 50:
            print("[DEBUG ML] Pas assez de résultats pour suggestion ML")
            return ""

        prompt = f"""CONTEXTE: L'utilisateur a un profil de type '{profile}'.
TÂCHE: Parmi les événements suivants, lequel est LE MEILLEUR pour lui ?

RÉSULTATS:
{current_results[:2000]}

INSTRUCTION: 
1. Isole UN SEUL événement de la liste
2. Explique en UNE PHRASE pourquoi ça correspond à son profil

FORMAT DE RÉPONSE ATTENDU:
🤖 **SUGGESTION PERSONNALISÉE ({profile})**
💡 *[Une phrase courte expliquant le choix]*
1. **[Titre exact]**
📅 [Date]
📍 [Lieu]
💰 [Prix]
🔗 [Lien]
Description: [Description]"""

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
        # 1. Définir les catégories opposées pour chaque profil
        opposites = {
            "Fêtard": ["nature", "art"],
            "Sportif": ["art", "theatre"],
            "Culturel": ["sport", "party"],
            "Cinéphile": ["sport", "nature"],
            "Chill": ["party", "sport"],
            "Curieux": ["art", "sport"]
        }
        
        # 2. Choisir une catégorie opposée aléatoire
        import random
        choices = opposites.get(profile, ["art"])
        target_category = random.choice(choices)
        
        print(f"[DEBUG NOVELTY] Profil: {profile} -> Catégorie opposée: {target_category}")
        
        # 3. Chercher des événements dans cette catégorie (VRAIS événements des APIs)
        events_text = fetch_all_events(target_category)
        
        if "Aucun événement" in events_text or "CATEGORY_ERROR" in events_text:
            print(f"[DEBUG NOVELTY] Aucun événement trouvé pour {target_category}")
            return ""

        # 4. Demander au LLM de choisir UN événement et le présenter
        prompt = f"""CONTEXTE: L'utilisateur a un profil '{profile}'.
TÂCHE: Propose-lui UNE activité '{target_category}' pour sortir de sa routine (Osez la nouveauté!).

RÉSULTATS DISPONIBLES:
{events_text[:2000]}

INSTRUCTION:
1. Choisis UN SEUL événement pertinent dans la liste
2. Explique en UNE PHRASE pourquoi c'est bien pour changer

FORMAT DE RÉPONSE ATTENDU:
🎲 **OSEZ LA NOUVEAUTÉ !**
💡 *[Une phrase courte expliquant pourquoi ça le change]*
1. **[Titre exact]**
📅 [Date]
📍 [Lieu]
💰 [Prix]
🔗 [Lien]
Description: [Description]"""

        try:
            response = self.llm.invoke(prompt)
            novelty = str(response.content) if hasattr(response, 'content') else str(response)
            print(f"[DEBUG NOVELTY] Générée: {novelty[:100]}...")
            return "\n\n" + novelty
        except Exception as e:
            print(f"[DEBUG NOVELTY] Erreur: {e}")
            return ""

    def _add_ml_suggestions_to_response(self, response: str, profile: str) -> str:
        """
        Ajoute les suggestions ML en utilisant des VRAIS événements des APIs.
        1. Suggestion personnalisée: LLM choisit le meilleur événement des résultats actuels
        2. Osez la Nouveauté: LLM cherche une catégorie opposée au profil
        """
        enhanced = response
        
        # 1. Suggestion personnalisée (parmi les résultats courants trouvés)
        if "📅" in response or "**" in response:  # Vérifier qu'il y a des résultats
            ml_suggestion = self._generate_ml_suggestion(response, profile)
            enhanced += ml_suggestion
        
        # 2. Osez la Nouveauté (chercher une catégorie opposée)
        novelty_section = self._generate_novelty(profile)
        enhanced += novelty_section
        
        return enhanced

    def _force_reformat_with_llm(self, raw_text: str) -> str:
        """Force le reformatage en demandant au LLM de réécrire au format strict (max 5 événements)."""
        if not raw_text:
            return raw_text
        prompt = f"""Reformate les événements ci-dessous AU FORMAT STRICT. Ne garde que 5 événements max.

Texte à reformater :
{raw_text[:5000]}

RÈGLES DE FORMAT (OBLIGATOIRE) :
1. **Titre**
📅 Date
📍 Lieu
💰 Prix (ou 'Gratuit' / 'Prix non précisé')
🔗 URL complète (http/https). Si absente, écrire 'Lien non disponible'
Description: Texte exact et complet

CONTRAINTES :
- Chaque info sur sa propre ligne (pas deux infos sur la même ligne)
- Une ligne vide entre chaque événement
- Pas de puces '❤️' ni tirets en tête de ligne, seulement la numérotation 1., 2., etc.
- Garde le texte en français
- Pas d'explications supplémentaires, seulement la liste formatée
"""
        try:
            resp = self.llm.invoke(prompt)
            return resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            print(f"[DEBUG] Reformat LLM failed: {e}")
            return raw_text

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
        
        FLUX:
        1. Déduire le profil de l'utilisateur (Fêtard, Culturel, etc.)
        2. Exécuter l'agent pour les résultats principaux
        3. Ajouter Suggestion Personnalisée (LLM choisit le meilleur des résultats)
        4. Ajouter Osez la Nouveauté (LLM cherche catégorie opposée)
        5. Formatter en HTML
        """
        try:
            # Step 0: Profil optionnel passé via tag [PROFILE:XXX]
            tag_profile, clean_msg = self._extract_profile_tag(user_input)
            profile = tag_profile or self._detect_profile_context(user_input)
            print(f"[DEBUG] Profil détecté: {profile} (tag={tag_profile})")
            
            # Step 2: Exécuter l'agent principal pour trouver les événements
            raw_response = self.agent.run(input=clean_msg)
            
            # Step 2.1: Forcer le reformatage par LLM (max 5 événements)
            raw_response = self._force_reformat_with_llm(raw_response)
            
            # Step 2.5: Vérifier s'il y a une erreur de catégorie
            if "CATEGORY_ERROR:" in raw_response:
                return self._format_response_to_html(raw_response.replace("CATEGORY_ERROR:", "❌"), "General")
            
            # Step 3: Ajouter les suggestions ML (avec VRAIS événements)
            enhanced_response = self._add_ml_suggestions_to_response(raw_response, profile)
            
            # Step 4: Formatter en HTML
            return self._format_response_to_html(enhanced_response, "General")
            
        except Exception as e:
            print(f"[ERROR] Erreur dans chat(): {e}")
            import traceback
            traceback.print_exc()
            return f"<p>Une erreur est survenue: {str(e)}</p>"