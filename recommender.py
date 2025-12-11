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
            # Si le CSV n'existe pas, on lance une erreur explicite
            raise FileNotFoundError(f"Le fichier {self.dataset_path} est introuvable. Lance 'generate_data.py' d'abord.")
            
        self.df = pd.read_csv(self.dataset_path)
        
        # On extrait uniquement les colonnes chiffrées pour le ML
        X = self.df[self.feature_columns].values
        self.model.fit(X)
        print("🤖 Modèle KNN entraîné sur", len(self.df), "utilisateurs fictifs.")

    def find_similar_user(self, user_preferences):
        """Trouve le voisin le plus proche (Profil Similaire)"""
        # Conversion du vecteur dict -> list ordonnée
        query_vector = []
        for col in self.feature_columns:
            query_vector.append(user_preferences.get(col, 0.0))
        
        query_vector = np.array(query_vector).reshape(1, -1)
        
        # Trouver le voisin
        distances, indices = self.model.kneighbors(query_vector)
        
        neighbor_idx = indices[0][0]
        neighbor_dist = distances[0][0]
        neighbor_data = self.df.iloc[neighbor_idx]
        
        return {
            "matched_user_id": neighbor_data["User_ID"],
            "matched_archetype": neighbor_data["Archetype"],
            "similarity_score": round(1 - neighbor_dist, 4),
            "recommended_activity_type": neighbor_data["Favorite_Event"] 
            # Note: On utilise ça comme "Type" d'activité, pas comme événement absolu
        }

    def find_routine_breaker(self, user_preferences):
        """
        Trouve une activité 'Anti-Routine' basée sur la catégorie la plus faible de l'utilisateur.
        """
        # 1. Trouver la catégorie avec le score le plus bas
        lowest_category = min(user_preferences, key=user_preferences.get)
        
        # 2. Trouver un profil dans le dataset qui est fort dans cette catégorie (> 0.7)
        opposites = self.df[self.df[lowest_category] > 0.7]
        
        if opposites.empty:
            # Fallback si personne n'est > 0.7
            opposites = self.df[self.df[lowest_category] > 0.5]
            
        # 3. Choisir un user au hasard dans ces opposés
        if not opposites.empty:
            opposite_user = opposites.sample(1).iloc[0]
            return {
                "category": lowest_category,
                "archetype": opposite_user["Archetype"],
                "activity_type": opposite_user["Favorite_Event"],
                "reason": f"Vous explorez peu la catégorie '{lowest_category}'"
            }
        
        return None