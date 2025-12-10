import os
from flask import Flask, render_template, request, jsonify
from agent import SocialAgentLangChain
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
agent = SocialAgentLangChain()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message vide'}), 400
        
        # Gestion des commandes spéciales
        if user_message.lower() in ['reset', 'recommencer', 'nouveau']:
            agent.reset_conversation()
            response = "Conversation réinitialisée ! Prêt pour une nouvelle recherche 🔍"
        else:
            response = agent.chat(user_message)
        
        return jsonify({'response': response})
        
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500

@app.route('/reset', methods=['POST'])
def reset_chat():
    agent.reset_conversation()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)