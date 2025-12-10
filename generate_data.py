import pandas as pd
import numpy as np
import random

# On définit des "Activités Piliers". 
# Ce ne sont pas des événements API en temps réel, mais des "Goûts"
ARCHETYPES = {
    "Culturel": {
        "Music": 0.2, "Sport": 0.1, "Cinema": 0.6, "Art": 0.9, "Nature": 0.3, 
        "Fav_Activities": [
            "Visite nocturne du Musée Magritte", 
            "Exposition immersive aux Beaux-Arts",
            "Opéra à la Monnaie",
            "Vernissage galerie Louise"
        ]
    },
    "Sportif": {
        "Music": 0.4, "Sport": 0.9, "Cinema": 0.2, "Art": 0.1, "Nature": 0.8, 
        "Fav_Activities": [
            "Les 20km de Bruxelles", 
            "Match des Diables Rouges au Stade Roi Baudouin",
            "Session d'escalade en salle",
            "Tournoi de Padel amateur"
        ]
    },
    "Fêtard": {
        "Music": 0.9, "Sport": 0.3, "Cinema": 0.4, "Art": 0.2, "Nature": 0.1, 
        "Fav_Activities": [
            "Concert Electro au Fuse", 
            "Soirée année 80 au Mirano",
            "Festival Tomorrowland",
            "Barathon place du Luxembourg"
        ]
    },
    "Cinéphile": {
        "Music": 0.3, "Sport": 0.1, "Cinema": 0.95, "Art": 0.5, "Nature": 0.2, 
        "Fav_Activities": [
            "Festival du Film Fantastique (BIFFF)", 
            "Rétrospective Kubrick à la Cinematek",
            "Avant-première au Grand Rex",
            "Marathon Harry Potter"
        ]
    },
    "Chill": {
        "Music": 0.5, "Sport": 0.2, "Cinema": 0.3, "Art": 0.2, "Nature": 0.9, 
        "Fav_Activities": [
            "Pique-nique au Bois de la Cambre", 
            "Balade vélo Forêt de Soignes",
            "Lecture au Parc Royal",
            "Marché aux plantes des Halles"
        ]
    }
}

def generate_users(n_users=100):
    data = []
    
    for i in range(n_users):
        # 1. Choisir un archétype
        archetype_name = random.choice(list(ARCHETYPES.keys()))
        base_vector = ARCHETYPES[archetype_name]
        
        # 2. Choisir une activité favorite aléatoire parmi celles de l'archétype
        fav_activity = random.choice(base_vector["Fav_Activities"])
        
        # 3. Créer le vecteur avec un peu de variation (Bruit)
        # On ajoute du random pour que User_1 ne soit pas identique à User_2
        user_vector = {
            "User_ID": f"User_{i+1}",
            "Archetype": archetype_name, 
            "Music":  min(1.0, max(0.0, base_vector["Music"] + np.random.normal(0, 0.15))),
            "Sport":  min(1.0, max(0.0, base_vector["Sport"] + np.random.normal(0, 0.15))),
            "Cinema": min(1.0, max(0.0, base_vector["Cinema"] + np.random.normal(0, 0.15))),
            "Art":    min(1.0, max(0.0, base_vector["Art"] + np.random.normal(0, 0.15))),
            "Nature": min(1.0, max(0.0, base_vector["Nature"] + np.random.normal(0, 0.15))),
            "Favorite_Event": fav_activity
        }
        data.append(user_vector)
        
    return pd.DataFrame(data)

if __name__ == "__main__":
    df = generate_users(100) # On génère 100 utilisateurs fictifs
    df.to_csv("users_dataset.csv", index=False)
    print("✅ Fichier 'users_dataset.csv' généré !")
    print(f"Exemple de profil généré : \n{df.iloc[0]}")