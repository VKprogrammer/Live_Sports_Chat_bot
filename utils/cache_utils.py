import os
import json
import sys
import time
import traceback
import numpy as np
import faiss
from config import (
    CACHE_DIR, CACHE_INDEX_FILE, CACHE_MAPPING_FILE, 
    CACHE_SIMILARITY_THRESHOLD, EMBEDDING_DIM
)

# Global variables
faiss_index = None
index_id_to_data = {}
next_faiss_id = 0

def normalize_query_for_filename(query: str) -> str:
    """Creates a safe filename hash from a query."""
    import hashlib
    return hashlib.sha1(query.encode('utf-8')).hexdigest()

def save_faiss_cache():
    """Saves the current FAISS index and mapping to disk."""
    global faiss_index, index_id_to_data, next_faiss_id
    
    if faiss_index and next_faiss_id > 0 and faiss_index.ntotal > 0:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            print(f"   Saving FAISS index ({faiss_index.ntotal} vectors) to {CACHE_INDEX_FILE}...")
            faiss.write_index(faiss_index, CACHE_INDEX_FILE)

            print(f"   Saving FAISS mapping ({len(index_id_to_data)} items) to {CACHE_MAPPING_FILE}...")
            save_data = {"next_id": next_faiss_id, "mapping": {str(k): v for k, v in index_id_to_data.items()}}
            with open(CACHE_MAPPING_FILE, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            print("   ✅ FAISS cache saved successfully.")
        except Exception as e:
            print(f"   ⚠️ Error saving FAISS cache: {type(e).__name__} - {e}", file=sys.stderr)
    elif faiss_index is not None:
         print("   Skipping FAISS cache save: Index is empty or next_faiss_id is 0.")
    else:
         print("   Skipping FAISS cache save: Index not initialized.")

def load_faiss_cache():
    """
    Loads the FAISS index and mapping from disk. Returns the loaded/initialized components.
    """
    global faiss_index, index_id_to_data, next_faiss_id
    
    if faiss_index is not None:
        return faiss_index, index_id_to_data, next_faiss_id
    
    if os.path.exists(CACHE_INDEX_FILE) and os.path.exists(CACHE_MAPPING_FILE):
        try:
            print(f"   Attempting to load FAISS index from {CACHE_INDEX_FILE}...")
            faiss_index = faiss.read_index(CACHE_INDEX_FILE)
            print(f"   FAISS index loaded ({faiss_index.ntotal} vectors).")

            print(f"   Attempting to load FAISS mapping from {CACHE_MAPPING_FILE}...")
            with open(CACHE_MAPPING_FILE, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            index_id_to_data = {int(k): v for k, v in loaded_data.get("mapping", {}).items()}
            next_faiss_id = loaded_data.get("next_id", 0)
            print(f"   FAISS mapping loaded ({len(index_id_to_data)} items, next_id: {next_faiss_id}).")

            # Consistency Check
            if faiss_index.ntotal != len(index_id_to_data):
                print(f"   ⚠️ FAISS cache inconsistency: Index size ({faiss_index.ntotal}) != Mapping size ({len(index_id_to_data)}). Resetting.", file=sys.stderr)
                raise ValueError("Cache inconsistency: Index size mismatch")
            if faiss_index.ntotal != next_faiss_id and next_faiss_id != 0:
                 print(f"   ⚠️ FAISS cache potential inconsistency: Index size ({faiss_index.ntotal}) != Next ID ({next_faiss_id}).", file=sys.stderr)

            print(f"   ✅ FAISS cache loaded successfully ({faiss_index.ntotal} items).")
            return faiss_index, index_id_to_data, next_faiss_id

        except FileNotFoundError:
            print(f"   Cache files not found. Initializing fresh cache.", file=sys.stderr)
        except Exception as e:
            print(f"   ⚠️ Error loading FAISS cache: {type(e).__name__} - {e}. Initializing fresh cache.", file=sys.stderr)

    print("   Initializing new FAISS index (IndexFlatIP).")
    faiss_index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index_id_to_data = {}
    next_faiss_id = 0
    return faiss_index, index_id_to_data, next_faiss_id

def get_cache_info():
    """Get information about the cache for display"""
    load_faiss_cache()  # Ensure cache is loaded
    
    return {
        "status": "Loaded" if faiss_index is not None else "Not Loaded",
        "items": faiss_index.ntotal if faiss_index is not None else "N/A",
        "directory": os.path.abspath(CACHE_DIR),
        "threshold": CACHE_SIMILARITY_THRESHOLD
    }

def get_from_cache(query, query_vector):
    """Try to get a result from the cache"""
    global faiss_index, index_id_to_data
    
    # Ensure cache is loaded
    load_faiss_cache()
    
    if faiss_index.ntotal == 0:
        return None, -1.0
    
    try:
        # Normalize the query vector
        faiss.normalize_L2(query_vector.reshape(1, -1))
        
        # Search for similar queries
        D, I = faiss_index.search(query_vector.reshape(1, -1), 1)
        
        if I.size > 0 and D.size > 0:
            nearest_neighbor_id = int(I[0][0])
            similarity_score = float(D[0][0])
            
            if similarity_score >= CACHE_SIMILARITY_THRESHOLD:
                if nearest_neighbor_id in index_id_to_data:
                    cached_query_str, cached_filepath = index_id_to_data[nearest_neighbor_id]
                    
                    if os.path.exists(cached_filepath):
                        with open(cached_filepath, 'r', encoding='utf-8') as f:
                            cached_data = json.load(f)
                        
                        # Clean up internal fields
                        cached_data.pop('_cached_original_query', None)
                        cached_data.pop('_cache_timestamp', None)
                        cached_data['_cache_status'] = f'HIT (Similarity: {similarity_score:.4f})'
                        
                        return cached_data, similarity_score
    except Exception as e:
        print(f"Error retrieving from cache: {e}", file=sys.stderr)
    
    return None, -1.0

def add_to_cache(query, query_vector, result_data):
    """Add a query and its result to the cache"""
    global faiss_index, index_id_to_data, next_faiss_id
    
    # Ensure cache is loaded
    load_faiss_cache()
    
    query_hash = normalize_query_for_filename(query)
    cache_filepath = os.path.join(CACHE_DIR, f"{query_hash}.json")
    
    try:
        # Save result data to file
        result_to_save = result_data.copy()
        result_to_save['_cached_original_query'] = query
        result_to_save['_cache_timestamp'] = time.time()
        
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            json.dump(result_to_save, f, indent=2, ensure_ascii=False)
        
        # Add to FAISS index
        if query_vector is not None:
            current_id = next_faiss_id
            faiss_index.add(query_vector.reshape(1, -1))
            index_id_to_data[current_id] = [query, cache_filepath]
            next_faiss_id += 1
            save_faiss_cache()
            return True
    except Exception as e:
        print(f"Error adding to cache: {e}", file=sys.stderr)
    
    return False
