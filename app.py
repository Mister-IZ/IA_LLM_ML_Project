import os
from flask import Flask, render_template, request, jsonify
from agent import SocialAgentLangChain
from recommender import SocialRecommender # On importe ton nouveau moteur
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
agent = SocialAgentLangChain()

# Initialisation du moteur de recommandation
try:
    rec_engine = SocialRecommender()
    print("✅ Moteur de recommandation chargé avec succès")
except Exception as e:
    print(f"⚠️ Erreur chargement recommandation: {e}")
    rec_engine = None

# --- ÉTAT GLOBAL UTILISATEUR (Pour la démo PoC) ---
# Dans une vraie app, cela serait stocké en base de données ou session utilisateur
user_profile = {
    "vector": {"Music": 0.1, "Sport": 0.1, "Cinema": 0.1, "Art": 0.1, "Nature": 0.1},
    "neighbor": None
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/onboarding', methods=['POST'])
def onboarding():
    """Reçoit les 3 préférences top de l'utilisateur et initialise le vecteur"""
    data = request.json
    choices = data.get('choices', []) # Ex: ['Cinema', 'Sport', 'Nature']
    
    # 1. Réinitialiser le vecteur avec un bruit de fond faible
    user_profile["vector"] = {"Music": 0.1, "Sport": 0.1, "Cinema": 0.1, "Art": 0.1, "Nature": 0.1}
    
    # 2. Appliquer les poids (Top 1 = fort, Top 3 = faible)
    weights = [0.8, 0.5, 0.3] # Poids à ajouter
    
    for i, category in enumerate(choices):
        if i < len(weights) and category in user_profile["vector"]:
            user_profile["vector"][category] += weights[i]
            # On cap à 1.0 maximum
            if user_profile["vector"][category] > 1.0: user_profile["vector"][category] = 1.0
            
    # 3. Trouver le voisin le plus proche (Machine Learning)
    if rec_engine:
        neighbor = rec_engine.find_similar_user(user_profile["vector"])
        user_profile["neighbor"] = neighbor
        
        # Petit message d'accueil personnalisé par l'agent
        welcome_prompt = f"""
        L'utilisateur vient de définir son profil.
        Ses intérêts majeurs sont : {', '.join(choices)}.
        Le profil similaire trouvé dans la base de données est : {neighbor['matched_user_id']} ({neighbor['matched_archetype']}).
        Activité recommandée : {neighbor['recommended_activity']}.
        
        Fais une phrase d'accueil courte et chaleureuse (max 2 phrases) qui mentionne subtilement l'activité recommandée.
        """
        welcome_msg = agent.agent.run(welcome_prompt)
        
        return jsonify({
            "status": "success", 
            "vector": user_profile["vector"],
            "neighbor": neighbor,
            "message": welcome_msg
        })
    
    return jsonify({"status": "error", "message": "Moteur ML non disponible"})

@app.route('/like', methods=['POST'])
def like_event():
    """L'utilisateur a aimé un événement, on met à jour son vecteur"""
    data = request.json
    text_content = data.get('text', '').lower()
    
    # Détection basique de la catégorie de l'événement liké
    category_found = None
    keywords = {
        "Music": ['concert', 'musique', 'jazz', 'rock', 'playlist', 'chant', 'karaoke'],
        "Sport": ['match', 'course', 'yoga', 'sport', 'ballon', 'stade', 'marathon'],
        "Cinema": ['film', 'cinéma', 'projection', 'théâtre', 'acteur', 'scène'],
        "Art": ['expo', 'musée', 'peinture', 'art', 'galerie', 'vernissage', 'dessin'],
        "Nature": ['balade', 'parc', 'fleur', 'plantes', 'jardin', 'forêt', 'écologie']
    }
    
    for cat, words in keywords.items():
        if any(w in text_content for w in words):
            category_found = cat
            break
    
    if category_found:
        # On renforce cette catégorie
        current_val = user_profile["vector"][category_found]
        user_profile["vector"][category_found] = min(1.0, current_val + 0.15) # +15% d'intérêt
        
        # On recalcule le voisin
        new_neighbor = None
        if rec_engine:
            new_neighbor = rec_engine.find_similar_user(user_profile["vector"])
            user_profile["neighbor"] = new_neighbor
            
        return jsonify({
            "status": "success",
            "updated_category": category_found,
            "new_vector": user_profile["vector"],
            "new_neighbor": new_neighbor
        })
        
    return jsonify({"status": "ignored", "message": "Catégorie non détectée"})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        if not user_message: return jsonify({'error': 'Message vide'}), 400
        
        # Reset simple
        if user_message.lower() in ['reset', 'recommencer', 'nouveau']:
            agent.reset_conversation()
            return jsonify({'response': "Conversation réinitialisée !"})
            
        # On ajoute le contexte du voisin trouvé au prompt système de manière invisible
        context_ml = ""
        if user_profile["neighbor"]:
            n = user_profile["neighbor"]
            context_ml = f"""
            [INFO ML: L'utilisateur ressemble au profil '{n['matched_archetype']}'. 
            Activité favorite typique de ce profil : {n['recommended_activity']}. 
            Essaie de pousser subtilement vers ce genre d'activités si pertinent.]
            """
            # On injecte ça temporairement dans la mémoire ou le prompt
            # Pour faire simple ici, on l'ajoute au message user
            # (L'utilisateur ne le verra pas, mais l'agent oui)
            response = agent.chat(user_message + context_ml)
        else:
            response = agent.chat(user_message)
        
        return jsonify({'response': response})
        
    except Exception as e:
        print(e)
        return jsonify({'error': f'Erreur: {str(e)}'}), 500

@app.route('/reset', methods=['POST'])
def reset_chat():
    agent.reset_conversation()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)