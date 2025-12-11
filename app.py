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
    """Initialise le profil via les 3 choix de départ"""
    data = request.json
    choices = data.get('choices', [])
    
    # 1. Reset du vecteur
    user_profile["vector"] = {"Music": 0.1, "Sport": 0.1, "Cinema": 0.1, "Art": 0.1, "Nature": 0.1}
    
    # 2. Application des poids de départ (Forts pour définir une tendance immédiate)
    weights = [0.9, 0.6, 0.4]
    for i, category in enumerate(choices):
        if i < len(weights) and category in user_profile["vector"]:
            user_profile["vector"][category] = weights[i]

    # 3. Calcul du premier voisin
    if rec_engine:
        neighbor = rec_engine.find_similar_user(user_profile["vector"])
        user_profile["neighbor"] = neighbor

        welcome_prompt = f"""
        L'utilisateur vient de finir son inscription. Son profil dominant est '{neighbor['matched_archetype']}'.
        
        Rédige un message d'accueil qui respecte STRICTEMENT cette structure :

        1. Commence EXACTEMENT par : "Merci d'avoir répondu à ces 3 petites questions, maintenant on se connaît un peu plus 😉"
        
        2. Enchaîne avec cette phrase (ou une variation très proche) : "Si vous avez atterri ici, c'est que vous cherchez à reconnecter avec votre ville. Mon but est de briser l'isolement en vous proposant des activités locales inclusives pour booster votre bien-être."
        
        3. Termine par une phrase courte invitant à demander une activité (en lien avec son profil '{neighbor['matched_archetype']}').
        
        Ne mets pas de titre, juste le texte.
        """
        
        # Message d'accueil
        msg = agent.agent.run(welcome_prompt)
        
        return jsonify({
            "status": "success", 
            "vector": user_profile["vector"], 
            "neighbor": neighbor, 
            "message": msg
        })
    
    return jsonify({"status": "error", "message": "ML Engine failure"})

@app.route('/like', methods=['POST'])
def like_event():
    """Gère le Like : Augmentation de la catégorie cible + Décroissance des autres (Decay)"""
    data = request.json
    text = data.get('text', '').lower()
    # On récupère la catégorie envoyée par le frontend (plus fiable que le texte)
    category_forced = data.get('category', None) 
    
    cat_found = None
    
    # 1. Identification de la catégorie
    if category_forced and category_forced in user_profile["vector"]:
        cat_found = category_forced
    else:
        # Fallback : détection par mots-clés si pas de catégorie fournie
        keywords = {
            "Music": ['concert', 'musique', 'jazz', 'rock', 'playlist'],
            "Sport": ['match', 'course', 'yoga', 'sport', 'ballon', 'stade'],
            "Cinema": ['film', 'cinéma', 'projection', 'théâtre', 'spectacle'],
            "Art": ['expo', 'musée', 'peinture', 'art', 'galerie', 'vernissage'],
            "Nature": ['balade', 'parc', 'fleur', 'plantes', 'jardin']
        }
        for cat, words in keywords.items():
            if any(w in text for w in words):
                cat_found = cat
                break
    
    if cat_found:
        # 2. LOGIQUE DE DYNAMISME & DECAY
        
        # A. Boost de la catégorie aimée (+0.25)
        # On ne dépasse pas 1.0
        user_profile["vector"][cat_found] = min(1.0, user_profile["vector"][cat_found] + 0.25)
        
        # B. Decay (Décroissance) des autres catégories (-0.05)
        # Cela permet au profil de changer radicalement si on change de comportement
        decay_rate = 0.05
        for category in user_profile["vector"]:
            if category != cat_found:
                current_val = user_profile["vector"][category]
                if current_val > 0.1: # On garde un plancher minimal
                    user_profile["vector"][category] = max(0.1, current_val - decay_rate)
        
        # 3. Recalcul immédiat du voisin (Live Update)
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
        
    return jsonify({"status": "ignored", "reason": "Catégorie non trouvée"})

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