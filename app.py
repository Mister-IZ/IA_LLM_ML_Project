import os
from flask import Flask, render_template, request, jsonify
from agent import SocialAgentLangChain
from recommender import SocialRecommender
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
agent = SocialAgentLangChain()

# Initialisation du moteur ML
try:
    rec_engine = SocialRecommender()
    print("✅ Moteur ML chargé avec succès")
except Exception as e:
    print(f"⚠️ Attention : Moteur ML non chargé ({e})")
    rec_engine = None

# État utilisateur GLOBAL (Pour la démo uniquement)
# Dans une vraie app, ce serait stocké par session utilisateur
user_profile = {
    "vector": {"Music": 0.1, "Sport": 0.1, "Cinema": 0.1, "Art": 0.1, "Nature": 0.1},
    "neighbor": None
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/onboarding', methods=['POST'])
def onboarding():
    data = request.json
    choices = data.get('choices', [])
    
    # 1. Reset & Poids (Inchangé)
    user_profile["vector"] = {"Music": 0.1, "Sport": 0.1, "Cinema": 0.1, "Art": 0.1, "Nature": 0.1}
    weights = [0.9, 0.6, 0.4]
    for i, category in enumerate(choices):
        if i < len(weights) and category in user_profile["vector"]:
            user_profile["vector"][category] = weights[i]

    # 2. ML & Message
    if rec_engine:
        neighbor = rec_engine.find_similar_user(user_profile["vector"])
        user_profile["neighbor"] = neighbor
        
        # --- LE MESSAGE D'ACCUEIL AVEC MENU ---
        # On ne demande plus au LLM de générer le texte, on met le tien pour être sûr du ton.
        
        welcome_text = f"""
        Merci d'avoir répondu à ces 3 petites questions, maintenant on vous connaît un peu plus 😉<br><br>
        
        Pour ton confort et afin que tu n'aies pas besoin de taper du texte, voici toutes les catégories d'activités que je peux te proposer. 
        Fais ton choix par rapport à ce que tu veux faire ! Pour moi l'essentiel c'est que tu trouves quelque chose que tu aimes bien afin que ça te motive à sortir et à sociabiliser.<br><br>
        
        Ne t'inquiète pas, au fur et à mesure on va de mieux en mieux se connaître de par les "like" que tu feras et je te proposerai toujours, parmi plusieurs activités, celle qui pour moi te va le mieux en fonction de ton profil.
        A mes yeux, pour l'instant comme je n'ai pu t'évaluer que sur ton top 3, je te vois comme un <strong>{neighbor['matched_archetype']}</strong>.
        <br><br>
        <strong>👇 Qu'est-ce qui te ferait plaisir aujourd'hui ?</strong>
        
        <div class="main-menu-container">
            <button class="menu-btn main" onclick="showSubMenu('music')">🎵 Musique & Concerts</button>
            <button class="menu-btn main" onclick="showSubMenu('culture')">🎨 Culture & Sorties</button>
            <button class="menu-btn main" onclick="showSubMenu('sport')">🏃 Sport & Bien-être</button>
            <button class="menu-btn main" onclick="showSubMenu('social')">🍻 Social & Gastronomie</button>
        </div>
        <div id="sub-menu-container" class="sub-menu-container"></div>
        """
        
        return jsonify({
            "status": "success", 
            "vector": user_profile["vector"], 
            "neighbor": neighbor, 
            "message": welcome_text
        })
    
    return jsonify({"status": "error"})

@app.route('/like', methods=['POST'])
def like_event():
    """Gère le Like avec priorité à l'analyse sémantique du titre"""
    data = request.json
    text = data.get('text', '').lower()
    category_forced = data.get('category', None) # Le contexte envoyé par le front (ex: Sport)
    
    cat_found = None
    
    # --- 1. ANALYSE SÉMANTIQUE (PRIORITÉ ABSOLUE) ---
    # Si le titre contient un mot-clé fort, on ignore le contexte de conversation
    # Cela règle le problème : "Je suis dans Sport, il me propose un Musée, je like -> Ça doit être Art"
    keywords = {
        "Music": ['concert', 'musique', 'jazz', 'rock', 'playlist', 'chanson', 'orchestre', 'nits', 'soprano', 'sheila', 'calogero'],
        "Sport": ['match', 'course', 'yoga', 'sport', 'ballon', 'stade', 'padel', 'fitness', 'training', 'karaté', 'zumba', 'badminton'],
        "Cinema": ['film', 'cinéma', 'projection', 'théâtre', 'spectacle', 'court métrage', 'documentaire'],
        "Art":    ['expo', 'musée', 'peinture', 'art', 'galerie', 'vernissage', 'beaux-arts', 'design'],
        "Nature": ['balade', 'parc', 'fleur', 'plantes', 'jardin', 'forêt', 'bois']
    }
    
    for cat, words in keywords.items():
        if any(w in text for w in words):
            cat_found = cat
            break
            
    # --- 2. FALLBACK SUR LE CONTEXTE ---
    # Si pas de mot-clé trouvé (ex: titre "Les Baronnes"), on fait confiance au contexte
    if not cat_found and category_forced and category_forced in user_profile["vector"]:
        cat_found = category_forced
    
    if cat_found:
        # A. Boost (+0.25)
        user_profile["vector"][cat_found] = min(1.0, user_profile["vector"][cat_found] + 0.25)
        
        # B. Decay (-0.05)
        decay_rate = 0.05
        for category in user_profile["vector"]:
            if category != cat_found:
                current_val = user_profile["vector"][category]
                if current_val > 0.1:
                    user_profile["vector"][category] = max(0.1, current_val - decay_rate)
        
        # C. Recalcul Voisin
        new_neighbor = None
        if rec_engine:
            new_neighbor = rec_engine.find_similar_user(user_profile["vector"])
            user_profile["neighbor"] = new_neighbor
            
        return jsonify({
            "status": "success",
            "updated_category": cat_found,
            "new_vector": user_profile["vector"],
            "new_neighbor": new_neighbor
        })
        
    return jsonify({"status": "ignored", "reason": "Catégorie indéterminée"})

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message', '').strip()
    if not user_msg: return jsonify({'error': 'Message vide'}), 400
    
    # Reset
    if user_msg.lower() in ['reset', 'recommencer', 'nouveau']:
        agent.reset_conversation()
        return jsonify({'response': "Conversation réinitialisée !"})
    
    # --- PRÉPARATION DU CONTEXTE ML INVISIBLE ---
    context_ml_instruction = ""
    
    if user_profile["neighbor"] and rec_engine:
        n = user_profile["neighbor"]
        
        # 1. On cherche l'Anti-Routine
        breaker = rec_engine.find_routine_breaker(user_profile["vector"])
        breaker_text = ""
        if breaker:
            breaker_text = f"""
            - AJOUTE UNE SECTION "🎲 OSEZ LA NOUVEAUTÉ !" À LA FIN.
              L'utilisateur ne fait jamais de '{breaker['category']}'.
              Suggère-lui d'essayer une activité de type '{breaker['category']}' (comme {breaker['activity_type']}).
              Si tu as trouvé un VRAI événement de ce type dans ta recherche API, propose-le. Sinon fais une suggestion générique.
            """

        # 2. On construit l'instruction Système
        # IMPORTANT : On dit à l'agent de piocher dans les résultats API, pas d'inventer
        context_ml_instruction = f"""
        [SYSTEM_HIDDEN_INSTRUCTION:
        Le profil ML de l'utilisateur est : '{n['matched_archetype']}'.
        
        SI (et seulement si) tu trouves des événements via tes outils (Recherche) :
        1. Affiche les résultats trouvés normalement.
        2. AJOUTE UNE SECTION "🤖 SUGGESTION PERSONNALISÉE ({n['matched_archetype']})" À LA FIN.
           -> Dans cette section, sélectionne UN événement parmi ceux que tu viens de trouver qui correspond le mieux à l'archétype '{n['matched_archetype']}'.
           -> Explique pourquoi tu l'as choisi.
        
        {breaker_text}
        
        SI l'utilisateur dit juste "Bonjour" ou pose une question hors-sujet, IGNORE ces instructions ML.
        ]
        """
    
    # On envoie le message + l'instruction cachée à l'agent
    response = agent.chat(user_msg + context_ml_instruction)
    
    return jsonify({'response': response})

@app.route('/reset', methods=['POST'])
def reset_chat():
    agent.reset_conversation()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)