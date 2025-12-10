import os
import json
import re
from typing import List, Dict, Any
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_mistralai import ChatMistralAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage
from tools import get_eventbrite_events, get_ticketmaster_events, get_brussels_events

class SocialAgentLangChain:
    def __init__(self):
        self.llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0.3,
            mistral_api_key=os.getenv("MISTRAL_API_KEY")
        )
        
        self.current_state = {
            "filter_type": None,
            "current_page": 1,
            "last_displayed_events": []
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
        return """Tu es un assistant bienveillant qui aide les personnes isolées à retrouver du lien social à Bruxelles.

    # FORMAT DE RÉPONSE STRICT - TU DOIS SUIVRE CE FORMAT EXACTEMENT

    ## Structure de la réponse :

    🎯 TITRE PRINCIPAL DE LA SECTION

    1. **NOM DE L'ÉVÉNEMENT**
    📅 Date et heure complètes
    📍 Lieu exact (adresse si possible)
    💰 Prix : Gratuit / Payant (précise le prix si connu)
    🔗 URL complète de l'événement
    
    Description courte et engageante (1-2 lignes)

    2. **DEUXIÈME ÉVÉNEMENT**
    📅 Date
    📍 Lieu
    💰 Prix
    🔗 Lien
    
    Description

    📌 SOUS-SECTION OU CONSEILS

    • Conseil 1 avec détails
    • Conseil 2 avec détails

    🌟 COUP DE CŒUR

    Description spéciale d'un événement remarquable

    ───────────────
    Séparateur visuel
    ───────────────

    ## RÈGLES ABSOLUES :

    1. TOUJOURS commencer les sections par 🎯, 📌 ou 🌟
    2. TOUJOURS utiliser le format exact ci-dessus pour les événements
    3. UNE ligne vide entre chaque événement
    4. Les descriptions doivent être courtes et engageantes
    5. Utiliser **gras** uniquement pour les noms d'événements
    6. TOUJOURS inclure les 4 icônes : 📅 📍 💰 🔗
    7. Pour "Gratuit" : écrire "🆓 GRATUIT" en majuscules
    8. Pour les liens : toujours mettre l'URL complète

    ## Exemple PARFAIT :

    🎯 ÉVÉNEMENTS MUSICAUX À BRUXELLES

    1. **Concert de Jazz au Botanique**
    📅 Vendredi 25 novembre 2024 à 20h
    📍 Botanique, Rue Royale 236, 1210 Bruxelles
    💰 15-25€ selon placement
    🔗 https://www.botanique.be/fr/events/concert-jazz
    
    Une soirée exceptionnelle avec les meilleurs musiciens de jazz de Belgique.

    📌 CONSEILS PRATIQUES

    • Arrivez 30 minutes avant pour profiter de l'ambiance

    🌟 NOTRE COUP DE CŒUR

    Le Concert de Jazz au Botanique offre une atmosphère intimiste.

    ───────────────

    Maintenant, utilise ce format EXACT pour toutes tes réponses."""

    def _setup_tools(self):
        def recherche_evenements_brussels(query: str) -> str:
            """Recherche des événements culturels à Bruxelles via l'API Brussels."""
            try:
                return get_brussels_events(query)
            except Exception as e:
                return f"Erreur avec l'API Brussels: {str(e)}"
        
        def recherche_evenements_ticketmaster(query: str) -> str:
            """Recherche des concerts et événements via Ticketmaster."""
            try:
                category_map = {
                    'musique': 'Music', 'concert': 'Music', 'music': 'Music',
                    'sport': 'Sports', 'sports': 'Sports', 'sportif': 'Sports',
                    'arts': 'Arts', 'art': 'Arts', 'culture': 'Arts',
                    'théâtre': 'Arts', 'theatre': 'Arts', 'spectacle': 'Arts',
                    'cinéma': 'Film', 'cinema': 'Film', 'film': 'Film',
                    'danse': 'Arts', 'dance': 'Arts'
                }
                category = 'Music'
                query_lower = query.lower()
                for key, value in category_map.items():
                    if key in query_lower:
                        category = value
                        break
                return get_ticketmaster_events(category)
            except Exception as e:
                return f"Erreur avec l'API Ticketmaster: {str(e)}"
        
        def recherche_evenements_eventbrite(query: str) -> str:
            """Recherche des ateliers et événements communautaires via EventBrite."""
            try:
                return get_eventbrite_events()
            except Exception as e:
                return f"Erreur avec l'API EventBrite: {str(e)}"

        return [
            Tool(
                name="RechercheEvenementsBrussels",
                func=recherche_evenements_brussels,
                description="Recherche des événements culturels locaux à Bruxelles. Utilise pour les activités communautaires, expositions, sports locaux, etc. Idéal pour les événements gratuits et sociaux."
            ),
            Tool(
                name="RechercheEvenementsTicketmaster",
                func=recherche_evenements_ticketmaster,
                description="Recherche des concerts, spectacles et événements payants. Utilise pour la musique, sports, arts. Donne les grands événements."
            ),
            Tool(
                name="RechercheEvenementsEventBrite", 
                func=recherche_evenements_eventbrite,
                description="Recherche des ateliers, formations et événements communautaires. Utilise pour les activités sociales et éducatives, rencontres."
            )
        ]
    
    def reset_conversation(self):
        """Réinitialise la conversation"""
        self.current_state = {
            "filter_type": None,
            "current_page": 1,
            "last_displayed_events": []
        }
        self.memory.clear()
    
    def _format_response_to_html(self, response: str) -> str:
        """Convertit la réponse de l'agent en HTML stylisé avec accordéon (Version Corrigée URL)"""
        if not response:
            return "<p>Aucune réponse générée.</p>"
        
        if 'suggestion-btn' in response:
             return self._inject_css() + '\n<div class="response-content">\n' + response + '\n</div>'

        cleaned = response.replace('```html', '').replace('```', '')
        
        html_parts = []
        lines = cleaned.split('\n')
        current_section = []
        in_list = False
        list_items = []
        current_hidden_info = [] 
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # --- GESTION DES TITRES ---
            if line.startswith('🎯') or line.startswith('📌') or line.startswith('🌟'):
                if list_items:
                    html_parts.append('<ul class="event-list">' + ''.join(list_items) + '</ul>')
                    list_items = []
                    in_list = False
                
                if current_section:
                    html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')
                    current_section = []
                
                if line.startswith('🎯'):
                    html_parts.append(f'<h2 class="section-title">{line}</h2>')
                elif line.startswith('📌'):
                    html_parts.append(f'<h3 class="section-subtitle">{line}</h3>')
                else:
                    html_parts.append(f'<h3 class="section-highlight">{line}</h3>')
                continue
            
            elif '─' in line and len(line) > 10:
                continue 
            
            # --- DÉBUT D'UN ÉVÉNEMENT ---
            elif re.match(r'^\d+\.\s+\*\*', line) or re.match(r'^\d+\.\s+[A-Z]', line):
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

                like_btn = '<button class="like-btn" onclick="toggleLike(this, \'' + content.replace("'", "\\'") + '\')">❤️</button>'

                list_items.append(f'<li class="event-item" onclick="toggleEvent(this)">{content} {like_btn}')
                in_list = True
                continue
            
            # --- DÉTAILS DE L'ÉVÉNEMENT ---
            elif in_list:
                # 1. Infos visibles (Date, Lieu, Prix)
                if line.startswith('📅') or line.startswith('📍') or line.startswith('💰') or line.startswith('🆓'):
                    list_items[-1] += f'<div class="event-detail">{line}</div>'
                
                # 2. Infos cachées (Lien) - CORRECTION ICI
                elif line.startswith('🔗'):
                    # Cas 1 : Lien Markdown [Texte](URL)
                    md_match = re.search(r'\[(.*?)\]\((https?://[^\)]+)\)', line)
                    if md_match:
                        url = md_match.group(2)
                        # On remplace tout par le bouton propre
                        line = f'<a href="{url}" target="_blank">Voir le site officiel</a>'
                    
                    # Cas 2 : Lien Brut https://...
                    elif 'http' in line:
                        url_match = re.search(r'(https?://[^\s]+)', line)
                        if url_match:
                            url = url_match.group(1)
                            line = f'<a href="{url}" target="_blank">Voir le site officiel</a>'
                    
                    current_hidden_info.append(f'<div class="event-detail link">{line}</div>')
                
                # 3. Description
                elif line and not any(line.startswith(x) for x in ['1.', '2.', '3.', '4.']):
                    current_hidden_info.append(f'<div class="event-description">{line}</div>')
                
            elif line:
                current_section.append(line)
        
        # --- FERMETURE ---
        if list_items:
            if current_hidden_info:
                list_items[-1] += f'<div class="more-info">{"".join(current_hidden_info)}</div>'
            list_items[-1] += '<div class="click-hint">🔽 Cliquez pour voir les détails</div></li>'
            html_parts.append('<ul class="event-list">' + ''.join(list_items) + '</ul>')
        
        if current_section:
            html_parts.append(f'<div class="section">{" ".join(current_section)}</div>')
        
        return self._inject_css() + '\n<div class="response-content">\n' + '\n'.join(html_parts) + '\n</div>'

    def _inject_css(self):
        """Retourne le CSS nécessaire pour le formatage interactif"""
        return """
        <style>
        .event-list { list-style: none; padding: 0; margin: 20px 0; }
        .event-item {
            background: white;
            border-left: 4px solid #007bff; padding: 20px; margin-bottom: 15px;
            border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            cursor: pointer; /* Indique qu'on peut cliquer */
            transition: all 0.2s ease;
        }
        .event-item:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); background-color: #f8f9fa; }
        .event-item strong { color: #2c3e50; font-size: 1.1em; display: block; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        
        .event-detail { margin: 5px 0; padding-left: 25px; color: #555; position: relative; }
        .more-info { 
            display: none; /* CACHÉ PAR DÉFAUT */
            margin-top: 15px; 
            padding-top: 15px; 
            border-top: 1px dashed #ddd; 
            animation: fadeIn 0.3s;
        }
        .event-item.active .more-info { display: block; /* VISIBLE QUAND ACTIF */ }
        .event-item.active { border-left-color: #28a745; background-color: #fff; }
        
        .event-description { margin-top: 10px; font-style: italic; color: #444; line-height: 1.5; background: #f1f3f5; padding: 10px; border-radius: 5px; }
        
        .click-hint { font-size: 0.8em; color: #999; text-align: center; margin-top: 10px; text-transform: uppercase; letter-spacing: 1px; }
        .event-item.active .click-hint { display: none; }

        .like-btn {
            float: right;
            background: none;
            border: 1px solid #ddd;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2em;
            padding: 5px 8px;
            transition: all 0.2s;
            z-index: 10;
            position: relative;
        }
        .like-btn:hover { transform: scale(1.2); background-color: #ffe6e6; border-color: #ff9999; }
        .like-btn.liked { background-color: #ff4757; color: white; border-color: #ff4757; }
        
        /* Boutons de suggestion */
        .suggestion-container { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 15px; margin-bottom: 15px; }
        .suggestion-btn {
            background-color: white; border: 1px solid #007bff; color: #007bff;
            padding: 8px 16px; border-radius: 20px; cursor: pointer; font-size: 0.9em;
            transition: all 0.2s; font-weight: 500;
        }
        .suggestion-btn:hover { background-color: #007bff; color: white; transform: scale(1.05); }

        @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
        </style>
        """

    def chat(self, message: str) -> str:
        """Interface de chat avec l'agent - Version avec Clarification Multi-Thématiques"""
        try:
            msg_lower = message.lower()
            
            # --- 1. LOGIQUE DE CLARIFICATION (DISAMBIGUATION) ---
            
            # 🎵 MUSIQUE : Concert vs Pratique
            if any(x in msg_lower for x in ['musique', 'zic', 'chanson']) and \
               not any(x in msg_lower for x in ['concert', 'jouer', 'écouter', 'voir', 'cours', 'atelier']):
                return self._format_response_to_html("""
    🎯 QUELLE EXPÉRIENCE MUSICALE CHERCHEZ-VOUS ?

    La musique se vit de plusieurs façons. Que préférez-vous ?

    <div class="suggestion-container">
        <button class="suggestion-btn" data-text="Je veux aller voir un concert">🎵 Aller voir un concert</button>
        <button class="suggestion-btn" data-text="Je veux jouer de la musique ou chanter">🎸 Jouer / Chanter (Jam, Chorale)</button>
        <button class="suggestion-btn" data-text="Je veux apprendre la musique">🎼 Prendre des cours</button>
    </div>
    """)

            # 🎬 CINÉMA : Film vs Théâtre vs Débat
            if 'cinéma' in msg_lower and not any(x in msg_lower for x in ['film', 'movie', 'théâtre', 'salle', 'voir']):
                return self._format_response_to_html("""
    🎯 PRÉCISONS VOS ENVIES

    Le monde du cinéma est vaste ! Pour vous proposer les meilleures activités :

    <div class="suggestion-container">
        <button class="suggestion-btn" data-text="Je cherche des films à l'affiche">🎬 Films à l'affiche</button>
        <button class="suggestion-btn" data-text="Je cherche des pièces de théâtre">🎭 Pièces de Théâtre</button>
        <button class="suggestion-btn" data-text="Je cherche des ciné-débats ou rencontres">🗣️ Ciné-débats / Rencontres</button>
    </div>
    """)

            # 🏃 SPORT : Regarder vs Pratiquer
            if 'sport' in msg_lower and not any(x in msg_lower for x in ['voir', 'regarder', 'faire', 'pratiquer', 'match', 'club']):
                return self._format_response_to_html("""
    🎯 QUEL TYPE DE SPORTIF ÊTES-VOUS ?

    Voulez-vous bouger ou supporter une équipe ?

    <div class="suggestion-container">
        <button class="suggestion-btn" data-text="Je veux aller voir un match">🏟️ Aller voir un match</button>
        <button class="suggestion-btn" data-text="Je veux faire du sport en groupe">🏃 Pratiquer une activité (Club, Cours)</button>
    </div>
    """)

            # 🎨 ART & CULTURE : Visite vs Création
            if any(x in msg_lower for x in ['art', 'culture', 'musée', 'expo']) and \
               not any(x in msg_lower for x in ['visiter', 'voir', 'atelier', 'créer', 'dessin']):
                return self._format_response_to_html("""
    🎯 ART & CULTURE

    Préférez-vous admirer des œuvres ou créer les vôtres ?

    <div class="suggestion-container">
        <button class="suggestion-btn" data-text="Je veux visiter une exposition">🖼️ Visiter une exposition</button>
        <button class="suggestion-btn" data-text="Je cherche un atelier créatif">🎨 Participer à un atelier créatif</button>
    </div>
    """)

            # --- 2. LOGIQUE DE RECHERCHE ---
            activity_keywords = ['activité', 'événement', 'évènement', 'sortie', 'faire', 
                            'trouve', 'cherche', 'propose', 'quoi', 'que', 'sport', 
                            'musique', 'concert', 'art', 'cinéma', 'théâtre', 'film',
                            'danse', 'spectacle', 'atelier', 'rencontre', 'match', 'cours', 
                            'voir', 'écouter', 'jouer', 'visiter', 'club', 'pratiquer']
            
            if any(keyword in msg_lower for keyword in activity_keywords):
                print(f"🔍 Recherche d'activités détectée: '{message}'")
                
                # Collecter les résultats des 3 APIs
                all_results = []
                
                # API Brussels (Culture locale, gratuit, sport local)
                try:
                    brussels = self.tools[0].func(message)
                    if brussels and "Aucun événement" not in brussels and "Erreur" not in brussels:
                        all_results.append("🎪 ÉVÉNEMENTS LOCAUX (API Brussels)\n\n" + brussels)
                except Exception as e:
                    print(f"⚠️ Erreur Brussels: {e}")
                
                # API Ticketmaster (Gros concerts, sport pro)
                try:
                    ticketmaster = self.tools[1].func(message)
                    if ticketmaster and "No events" not in ticketmaster and "Erreur" not in ticketmaster:
                        all_results.append("🎫 GRANDS ÉVÉNEMENTS (Ticketmaster)\n\n" + ticketmaster)
                except Exception as e:
                    print(f"⚠️ Erreur Ticketmaster: {e}")
                
                # API EventBrite (Ateliers, social, cours)
                try:
                    eventbrite = self.tools[2].func(message)
                    if eventbrite and "No events" not in eventbrite and "Erreur" not in eventbrite:
                        all_results.append("👥 ATELIERS & COMMUNAUTÉ (EventBrite)\n\n" + eventbrite)
                except Exception as e:
                    print(f"⚠️ Erreur EventBrite: {e}")
                
                if all_results:
                    combined = "\n\n───────────────\n\n".join(all_results)
                    
                    # Prompt strict avec format imposé
                    strict_prompt = f"""L'utilisateur recherche : "{message}"

    Voici les événements trouvés dans les 3 bases de données :

    {combined}

    Maintenant, formule une réponse EN FRANÇAIS en suivant STRICTEMENT ce format :

    🎯 TITRE GÉNÉRAL (adapté à la demande)

    1. **Nom Événement 1** (le plus pertinent)
    📅 Date et heure
    📍 Lieu
    💰 Prix
    🔗 Lien URL
    
    Description courte et engageante

    2. **Nom Événement 2** (deuxième plus pertinent)
    📅 Date
    📍 Lieu  
    💰 Prix
    🔗 Lien
    
    Description

    [Continue avec 3-5 événements maximum les plus pertinents]

    📌 CONSEILS POUR SOCIALISER

    • Conseil 1 spécifique au type d'activité
    • Conseil 2 pratique
    • Conseil 3 encourageant

    🌟 RECOMMANDATION SPÉCIALE

    Mets en avant l'événement le plus social/gratuit/accessible.

    ───────────────

    Sois bienveillant, précis, et respecte ABSOLUMENT le format ci-dessus. Utilise uniquement les événements de la liste fournie."""
                    
                    response = self.agent.run(strict_prompt)
                    return self._format_response_to_html(response)
                else:
                    return self._format_response_to_html("""
    🎯 RECHERCHE D'ÉVÉNEMENTS

    Désolé, je n'ai trouvé aucun événement correspondant à votre recherche dans nos bases de données pour le moment.

    📌 CONSEILS ALTERNATIFS

    • Essayez de reformuler votre recherche avec d'autres mots-clés
    • Consultez les sites officiels de la Ville de Bruxelles
    
    <div class="suggestion-container">
        <button class="suggestion-btn" data-text="Activités gratuites">🆓 Activités gratuites</button>
        <button class="suggestion-btn" data-text="Activités ce weekend">📅 Ce weekend</button>
    </div>
    """)
            
            # Pour les autres messages
            response = self.agent.run(message)
            return self._format_response_to_html(response)
            
        except Exception as e:
            error_html = f"""
    <div class="error-message">
        <h3>⚠️ Oups ! Une erreur s'est produite</h3>
        <p>Désolé, le service rencontre actuellement des difficultés techniques.</p>
        <p><em>Message technique : {str(e)[:100]}...</em></p>
    </div>
    """
            return error_html