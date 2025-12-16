"""
Like Handler Module
Handles the like/unlike logic for events with ML category detection.
"""

def handle_like(data, user_profile, agent=None, rec_engine=None):
    """
    Process a like/unlike action on an event.
    
    Args:
        data: Request JSON data with 'text', 'category', 'action'
        user_profile: Dict with 'vector' and 'neighbor' keys
        agent: Optional NewAgent instance for LLM classification
        rec_engine: Optional SocialRecommender instance
    
    Returns:
        Dict with status and updated data
    """
    print("=" * 50)
    print("[LIKE HANDLER] Called!")
    print("=" * 50)
    
    print(f"[DEBUG LIKE] Received data: {data}")
    
    # Extract data
    raw_text = data.get('text')
    text = raw_text.lower() if raw_text else ''
    category_forced = data.get('category', None)
    action = data.get('action', 'like')
    
    print(f"[DEBUG LIKE] text={text[:50] if text else 'None'}...")
    print(f"[DEBUG LIKE] category_forced={category_forced}")
    print(f"[DEBUG LIKE] action={action}")
    print(f"[DEBUG LIKE] user_profile vector keys: {list(user_profile['vector'].keys())}")
    
    cat_found = None
    
    # --- 1. PRIORITIZE FRONTEND CATEGORY (GREEN: No API call needed!) ---
    if category_forced:
        print(f"[DEBUG LIKE] Checking category_forced: '{category_forced}'")
        # Try exact match first
        if category_forced in user_profile["vector"]:
            cat_found = category_forced
            print(f"✅ Using frontend category directly: {cat_found}")
        else:
            # Case-insensitive fallback
            for key in user_profile["vector"]:
                if key.lower() == category_forced.lower():
                    cat_found = key
                    print(f"✅ Using frontend category (case-matched): {cat_found}")
                    break
    
    # --- 2. FALLBACK: LLM Classification (only if category not provided) ---
    if not cat_found and text and agent and hasattr(agent, '_detect_category_with_llm'):
        print(f"🌱 Using LLM to classify: '{text[:50]}...'")
        llm_cat = agent._detect_category_with_llm(text)
        category_mapping = {
            'music': 'Music', 'party': 'Music',
            'sport': 'Sport',
            'cinema': 'Cinema', 'theatre': 'Cinema',
            'art': 'Art',
            'nature': 'Nature', 'family': 'Nature',
        }
        cat_found = category_mapping.get(llm_cat, None)
        print(f"✅ LLM classified as: {cat_found}")
    
    # --- 3. FALLBACK: TF-IDF Green Classifier ---
    if not cat_found and text and rec_engine and hasattr(rec_engine, 'classify_text_green'):
        print(f"🌱 Fallback to Green Classifier: '{text[:50]}...'")
        cat_found = rec_engine.classify_text_green(text)
        print(f"✅ Green Classifier found: {cat_found}")
    
    # --- 4. No category found ---
    if not cat_found:
        print("⚠️ Aucune catégorie détectée pour ce Like.")
        return {
            "status": "ignored", 
            "message": "Catégorie indéterminée",
            "reason": "Catégorie indéterminée"
        }
    
    # --- 5. Update user vector ---
    print(f"[DEBUG LIKE] cat_found = {cat_found}, updating vector...")
    
    if action == 'like':
        user_profile["vector"][cat_found] = min(1.0, user_profile["vector"][cat_found] + 0.25)
        # Decay other categories slightly
        for category in user_profile["vector"]:
            if category != cat_found:
                current_val = user_profile["vector"][category]
                if current_val > 0.1:
                    user_profile["vector"][category] = max(0.1, current_val - 0.05)
    else:  # unlike
        user_profile["vector"][cat_found] = max(0.1, user_profile["vector"][cat_found] - 0.25)
        # Boost other categories slightly
        for category in user_profile["vector"]:
            if category != cat_found:
                user_profile["vector"][category] = min(1.0, user_profile["vector"][category] + 0.05)
    
    print(f"[DEBUG LIKE] Updated vector: {user_profile['vector']}")
    
    # Update agent's internal preferences
    if agent and hasattr(agent, 'like_event'):
        agent.like_event(cat_found.lower())
    
    # Find new neighbor
    new_neighbor = None
    if rec_engine:
        try:
            new_neighbor = rec_engine.find_similar_user(user_profile["vector"])
            user_profile["neighbor"] = new_neighbor
            print(f"[DEBUG LIKE] New neighbor: {new_neighbor}")
        except Exception as e:
            print(f"Error finding neighbor: {e}")
    
    response_data = {
        "status": "success",
        "message": f"✅ {action.capitalize()}d {cat_found}",
        "action": action,
        "updated_category": cat_found,
        "new_vector": user_profile["vector"],
        "new_neighbor": new_neighbor
    }
    print(f"[DEBUG LIKE] Returning: {response_data}")
    return response_data
