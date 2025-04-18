import numpy as np
import sys
import traceback

def get_embedding(text: str, task_type="RETRIEVAL_QUERY") -> np.ndarray:
    """Generates an embedding for the given text using the configured model."""
    # Import here to avoid circular imports
    from services.gemini_service import get_client
    
    client = get_client()
    if client is None:
        print("   ⚠️ Gemini client not initialized yet in get_embedding.", file=sys.stderr)
        return None
    
    if not text or not isinstance(text, str):
        print(f"   ⚠️ Invalid input for embedding: {type(text)}", file=sys.stderr)
        return None
    
    text = text.strip()
    if not text:
        return None

    try:
        from google.genai import types as genai_types
        response = client.models.embed_content(
            model="models/embedding-001",
            contents=[text],
            config=genai_types.EmbedContentConfig(task_type=task_type)
        )
        
        if response.embeddings and response.embeddings[0].values:
            return np.array(response.embeddings[0].values).astype('float32')
        else:
            print(f"   ⚠️ No embeddings returned from API for text snippet: '{text[:50]}...'", file=sys.stderr)
            return None
    except Exception as e:
        print(f"   ⚠️ Embedding generation failed: {type(e).__name__} - {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return None
