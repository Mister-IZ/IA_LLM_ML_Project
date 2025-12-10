import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
import os

class SocialRecommender:
    def __init__(self, dataset_path="users_dataset.csv"):
        self.dataset_path = dataset_path
        self.model = NearestNeighbors(n_neighbors=1, algorithm='brute', metric='cosine')
        self.df = None
        self.feature_columns = ["Music", "Sport", "Cinema", "Art", "Nature"]
        
        self._load_and_train()
    
    def _load_and_train(self):
        """Charge le dataset et entraîne le modèle KNN"""
        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"Le fichier {self.dataset_path} n'existe pas. Lancez generate_data.py d'abord.")
            
        self.df = pd.read_csv(self.dataset_path)
        
        # On extrait uniquement les colonnes chiffrées pour le ML
        X = self.df[self.feature_columns].values
        self.model.fit(X)
        print("🤖 Modèle KNN entraîné sur", len(self.df), "utilisateurs fictifs.")

    def find_similar_user(self, user_preferences):
        """
        Prend un dictionnaire de préférences utilisateur, 
        trouve le voisin le plus proche et retourne ses infos.
        """
        # Convertir les préférences en vecteur ordonné selon feature_columns
        # Exemple input: {"Cinema": 1.0, "Sport": 0.5, ...}
        query_vector = []
        for col in self.feature_columns:
            query_vector.append(user_preferences.get(col, 0.0))
        
        # Reshape pour scikit-learn (1 ligne, N colonnes)
        query_vector = np.array(query_vector).reshape(1, -1)
        
        # Trouver le voisin le plus proche
        distances, indices = self.model.kneighbors(query_vector)
        
        neighbor_idx = indices[0][0]
        neighbor_dist = distances[0][0]
        
        neighbor_data = self.df.iloc[neighbor_idx]
        
        return {
            "matched_user_id": neighbor_data["User_ID"],
            "matched_archetype": neighbor_data["Archetype"],
            "similarity_score": round(1 - neighbor_dist, 4), # Convertir distance en similarité (approx)
            "recommended_activity": neighbor_data["Favorite_Event"],
            "debug_vector": neighbor_data[self.feature_columns].to_dict()
        }

# Test rapide si on lance le fichier directement
if __name__ == "__main__":
    rec = SocialRecommender()
    # Imaginons un user qui aime le cinéma et l'art
    test_profile = {"Music": 0.1, "Sport": 0.0, "Cinema": 1.0, "Art": 0.8, "Nature": 0.2}
    print("Résultat pour profil test :", rec.find_similar_user(test_profile))