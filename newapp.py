import os
import threading
from flask import Flask, render_template, request, jsonify
from newAgent import NewAgent
from recommender import SocialRecommender
from like_handler import handle_like
from dotenv import load_dotenv
from toolsFolder.eventBriteTool import fetch_events_to_cache

load_dotenv()

app = Flask(__name__)

# --- Background Cache Warmup ---
def warmup_cache():
    print("⏳ Starting background EventBrite fetch...")
    try:
        fetch_events_to_cache(force_refresh=True)
        print("✅ Background EventBrite fetch completed!")
    except Exception as e:
        print(f"❌ Background fetch failed: {e}")

# Start the thread immediately
threading.Thread(target=warmup_cache, daemon=True).start()

# Initialize Agent
try:
    agent = NewAgent()
    print("✅ Agent initialized successfully")
except Exception as e:
    print(f"❌ Error initializing agent: {e}")
    agent = None

# Initialize ML Engine (Optional)
try:
    rec_engine = SocialRecommender()
    print("✅ ML Engine loaded successfully")
except Exception as e:
    print(f"⚠️ Warning: ML Engine not loaded ({e})")
    rec_engine = None

# Global User State (Demo only)
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
    
    # 1. Reset & Weights
    user_profile["vector"] = {"Music": 0.1, "Sport": 0.1, "Cinema": 0.1, "Art": 0.1, "Nature": 0.1}
    weights = [0.9, 0.6, 0.4]
    for i, category in enumerate(choices):
        if i < len(weights) and category in user_profile["vector"]:
            user_profile["vector"][category] = weights[i]

    # 2. ML & Message
    neighbor_info = {"matched_archetype": "New User"}
    if rec_engine:
        try:
            neighbor = rec_engine.find_similar_user(user_profile["vector"])
            user_profile["neighbor"] = neighbor
            neighbor_info = neighbor
        except Exception as e:
            print(f"Error finding similar user: {e}")

    welcome_text = f"""
    Merci d'avoir répondu à ces questions !<br><br>
    Je vois que tu es un profil de type <strong>{neighbor_info.get('matched_archetype', 'Explorateur')}</strong>.
    <br><br>
    <strong>👇 Qu'est-ce qui te ferait plaisir aujourd'hui ?</strong>
    
    <div class="main-menu-container">
        <button class="menu-btn main" onclick="showSubMenu('music')">🎵 Musique & Concerts</button>
        <button class="menu-btn main" onclick="showSubMenu('culture')">🎨 Culture & Sorties</button>
        <button class="menu-btn main" onclick="showSubMenu('sport')">🏃 Sport & Bien-être</button>
        <button class="menu-btn main" onclick="showSubMenu('nature')">🌳 Nature & Plein air</button>
    </div>
    <div id="sub-menu-container" class="sub-menu-container"></div>
    """
    
    return jsonify({
        "status": "success", 
        "vector": user_profile["vector"], 
        "neighbor": user_profile["neighbor"], 
        "message": welcome_text
    })

@app.route('/like', methods=['POST'])
def like_event():
    """Gère le Like/Unlike - Logic moved to like_handler.py"""
    result = handle_like(request.json, user_profile, agent, rec_engine)
    return jsonify(result)

@app.route('/chat', methods=['POST'])
def chat():
    if not agent:
        return jsonify({'error': 'Agent not initialized'}), 500

    user_msg = request.json.get('message', '').strip()
    if not user_msg: return jsonify({'error': 'Message vide'}), 400
    
    # Reset
    if user_msg.lower() in ['reset', 'recommencer', 'nouveau']:
        if hasattr(agent, 'reset_preferences'):
            agent.reset_preferences()
        elif hasattr(agent, 'memory'):
            agent.memory.clear()
        return jsonify({'response': "Conversation réinitialisée !"})
    
    # Sync user_profile to agent's internal preferences (for consistency)
    if hasattr(agent, 'user_preferences'):
        agent.user_preferences = user_profile["vector"].copy()
        agent.interaction_count = max(agent.interaction_count, 2)  # Ensure ML kicks in
    
    # Basic Chat - The agent now handles ML internally via _detect_category_with_llm
    # No need to inject hidden instructions anymore - it's all in the agent
    try:
        response = agent.chat(user_msg)
        
        # Sync back agent's updated preferences to user_profile
        if hasattr(agent, 'user_preferences'):
            user_profile["vector"] = agent.user_preferences.copy()
            # Update neighbor based on new preferences
            if rec_engine:
                try:
                    user_profile["neighbor"] = rec_engine.find_similar_user(user_profile["vector"])
                except:
                    pass
        
        return jsonify({'response': response})
    except Exception as e:
        print(f"Error in chat: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset_chat():
    if agent and hasattr(agent, 'memory'):
        agent.memory.clear()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # Initialize CodeCarbon Tracker
    from codecarbon import EmissionsTracker
    # on_csv_write="append" prevents overwriting/renaming to .bak
    tracker = EmissionsTracker(project_name="BrusselsEventAgent", output_dir="emissions.csv", on_csv_write="append")
    tracker.start()
    print("🌍 CodeCarbon Tracker Started!")
    
    try:
        app.run(debug=True, port=5000, use_reloader=False) # use_reloader=False to avoid double tracking in debug
    finally:
        tracker.stop()
        print("🌍 CodeCarbon Tracker Stopped. Emissions saved to emissions.csv")
