# -*- coding: utf-8 -*-
# streamlit_app.py (Single File Version - Using genai.Client as per Original Script)
"""
Streamlit User Interface and Core Logic for the Sports Chatbot.
Includes Gemini interaction, web scraping, and FAISS caching.
Uses genai.Client() and client.chats.create() for initialization.
"""

# --- Core Imports ---
import streamlit as st
import os
import time
import json
import re
import sys
import hashlib
import numpy as np
import traceback # For detailed error logging
from live_matches import display_live_matches
from dotenv import load_dotenv # For local dev

# --- Gemini Imports ---
try:
    import google.genai as genai
    # Ensure 'types' is imported correctly if needed by client.chats.create or embed_content config
    from google.genai import types as genai_types
    from google.generativeai.types import StopCandidateException
    print(f"Using google-genai SDK version: {genai.__version__}")
except ImportError as e:
    StopCandidateException = Exception
    if "google.generativeai" in str(e): st.error("WARNING: Specific StopCandidateException not found.")
    elif "google.genai" in str(e): st.error("ERROR: 'google-generativeai' package required."); st.stop()
    else: st.error(f"ERROR: Import error: {e}"); st.stop()
except Exception as e:
     st.error(f"ERROR: Failed to import google.genai: {e}"); st.stop()

# --- Web Scraping & Caching Imports ---
try:
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from bs4 import BeautifulSoup
    from urllib.parse import quote_plus
except ImportError as e:
    st.error(f"ERROR: Missing library ({e}). pip install selenium beautifulsoup4 lxml numpy faiss-cpu python-dotenv")
    st.stop()

try:
    import faiss
    print(f"Using FAISS version: {faiss.__version__}")
except ImportError:
    st.error("ERROR: FAISS library not found. pip install faiss-cpu")
    st.stop()

# --- Configuration ---
MODEL_NAME = "gemini-2.0-flash"
EMBEDDING_MODEL = "models/embedding-001"
EMBEDDING_DIM = 768
CACHE_DIR = "search_cache_v6_text_commentary"
CACHE_INDEX_FILE = os.path.join(CACHE_DIR, "faiss_index_v6.idx")
CACHE_MAPPING_FILE = os.path.join(CACHE_DIR, "faiss_mapping_v6.json")
CACHE_SIMILARITY_THRESHOLD = 0.96
WEBDRIVER_TIMEOUT = 25
LINK_LOAD_TIMEOUT = 15
CHROMEDRIVER_PATH = None

os.makedirs(CACHE_DIR, exist_ok=True)
print(f"Cache directory configured: {os.path.abspath(CACHE_DIR)}")

# --- Global variables ---
# Client will be initialized in the cached function
client = None
faiss_index = None
index_id_to_data = {}
next_faiss_id = 0

# --- Page Configuration ---
st.set_page_config(
    page_title="Sports Chatbot ⚽",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="auto"
)
# Create a two-column layout
col1, col2 = st.columns([2, 1])

# --- API Key Retrieval (from Streamlit Secrets) ---
# We need the key *before* initializing the client
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    if not GOOGLE_API_KEY:
        st.error("❌ Google API Key not found in Streamlit secrets! Add `GOOGLE_API_KEY = 'YOUR_KEY'` to `.streamlit/secrets.toml`.")
        st.stop()
    print("✅ Google API Key loaded from secrets.")
except KeyError:
    st.error("❌ `GOOGLE_API_KEY` not found in Streamlit secrets. Check `.streamlit/secrets.toml`.")
    print("❌ ERROR: GOOGLE_API_KEY not found in st.secrets", file=sys.stderr)
    st.stop()
except Exception as e:
    st.error(f"❌ Error retrieving Google API Key: {e}")
    print(f"❌ ERROR: Failed to get API Key: {e}", file=sys.stderr)
    st.stop()


# --- Helper Functions ---

def get_embedding(text: str, task_type="RETRIEVAL_QUERY") -> np.ndarray | None:
    """Generates an embedding for the given text using the configured model."""
    global client # Uses the globally assigned client
    if not client:
        print("   ⚠️ Gemini client (global) not initialized yet in get_embedding.", file=sys.stderr)
        # Attempt to show an error in UI if possible, otherwise just log and fail
        # st.error("Client not ready for embedding.") # Might cause issues if called outside main thread
        return None
    if not text or not isinstance(text, str):
        print(f"   ⚠️ Invalid input for embedding: {type(text)}", file=sys.stderr)
        return None
    text = text.strip()
    if not text: return None

    try:
        # Use the client object's method as per the original script
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=[text], # Pass as a list
            config=genai_types.EmbedContentConfig(task_type=task_type) # Use imported types
        )
        # Access response using dot notation as per client object methods
        if response.embeddings and response.embeddings[0].values:
            return np.array(response.embeddings[0].values).astype('float32')
        else:
            print(f"   ⚠️ No embeddings returned from API for text snippet: '{text[:50]}...'", file=sys.stderr)
            # print(f"   DEBUG Response: {response}") # Optional debug
            return None
    except Exception as e:
        print(f"   ⚠️ Embedding generation failed: {type(e).__name__} - {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return None

# --- Caching Utilities (normalize_query_for_filename, save_faiss_cache, load_faiss_cache) ---
# --- [ Keep these functions exactly as they were in the previous single-file version ] ---
def normalize_query_for_filename(query: str) -> str:
    """Creates a safe filename hash from a query."""
    return hashlib.sha1(query.encode('utf-8')).hexdigest()

def save_faiss_cache():
    """Saves the current FAISS index and mapping to disk."""
    global faiss_index, index_id_to_data, next_faiss_id # Uses global variables
    if faiss_index and next_faiss_id > 0 and faiss_index.ntotal > 0:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            print(f"   Saving FAISS index ({faiss_index.ntotal} vectors) to {CACHE_INDEX_FILE}...")
            faiss.write_index(faiss_index, CACHE_INDEX_FILE)

            print(f"   Saving FAISS mapping ({len(index_id_to_data)} items) to {CACHE_MAPPING_FILE}...")
            # Convert int keys to str for JSON
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
    local_faiss_index = None
    local_index_id_to_data = {}
    local_next_faiss_id = 0

    if os.path.exists(CACHE_INDEX_FILE) and os.path.exists(CACHE_MAPPING_FILE):
        try:
            print(f"   Attempting to load FAISS index from {CACHE_INDEX_FILE}...")
            local_faiss_index = faiss.read_index(CACHE_INDEX_FILE)
            print(f"   FAISS index loaded ({local_faiss_index.ntotal} vectors).")

            print(f"   Attempting to load FAISS mapping from {CACHE_MAPPING_FILE}...")
            with open(CACHE_MAPPING_FILE, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            # Convert str keys back to int
            local_index_id_to_data = {int(k): v for k, v in loaded_data.get("mapping", {}).items()}
            local_next_faiss_id = loaded_data.get("next_id", 0)
            print(f"   FAISS mapping loaded ({len(local_index_id_to_data)} items, next_id: {local_next_faiss_id}).")

            # Consistency Check
            if local_faiss_index.ntotal != len(local_index_id_to_data):
                print(f"   ⚠️ FAISS cache inconsistency: Index size ({local_faiss_index.ntotal}) != Mapping size ({len(local_index_id_to_data)}). Resetting.", file=sys.stderr)
                raise ValueError("Cache inconsistency: Index size mismatch")
            if local_faiss_index.ntotal != local_next_faiss_id and local_next_faiss_id != 0 :
                 print(f"   ⚠️ FAISS cache potential inconsistency: Index size ({local_faiss_index.ntotal}) != Next ID ({local_next_faiss_id}).", file=sys.stderr)

            print(f"   ✅ FAISS cache loaded successfully ({local_faiss_index.ntotal} items).")
            return local_faiss_index, local_index_id_to_data, local_next_faiss_id

        except FileNotFoundError:
            print(f"   Cache files not found. Initializing fresh cache.", file=sys.stderr)
        except Exception as e:
            print(f"   ⚠️ Error loading FAISS cache: {type(e).__name__} - {e}. Initializing fresh cache.", file=sys.stderr)

    print("   Initializing new FAISS index (IndexFlatIP).")
    local_faiss_index = faiss.IndexFlatIP(EMBEDDING_DIM)
    local_index_id_to_data = {}
    local_next_faiss_id = 0
    return local_faiss_index, local_index_id_to_data, local_next_faiss_id

# --- Web Scraping Function (_perform_web_search_and_extract) ---
# --- [ Keep this function exactly as it was ] ---
def _perform_web_search_and_extract(query: str) -> dict:
    """Internal function to perform web scraping using Selenium and BeautifulSoup."""
    print(f"\n[_perform_web_search_and_extract] Executing LIVE search for: '{query}'")
    scraped_data = {"_cache_status": "Live Search Triggered"}
    driver = None
    main_page_scraped = False
    links_scraped_count = 0
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
        options.page_load_strategy = 'eager'

        print("   Initializing WebDriver (live)...")
        try:
            if CHROMEDRIVER_PATH and os.path.exists(CHROMEDRIVER_PATH):
                service = Service(executable_path=CHROMEDRIVER_PATH)
                print(f"   Using specified ChromeDriver: {CHROMEDRIVER_PATH}")
            else:
                print("   Attempting to use ChromeDriver from system PATH.")
                service = Service()
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_script_timeout(WEBDRIVER_TIMEOUT)
            driver.implicitly_wait(5)
            print("   ✅ WebDriver initialized successfully (live).")
        except WebDriverException as e_init:
            error_msg = f"WebDriver initialization failed: {e_init}. Ensure ChromeDriver is installed/in PATH."
            print(f"   ❌ {error_msg}", file=sys.stderr)
            scraped_data["error"] = error_msg
            return scraped_data
        except Exception as e_init_other:
            error_msg = f"Unexpected error during WebDriver initialization: {e_init_other}"
            print(f"   ❌ {error_msg}", file=sys.stderr)
            scraped_data["error"] = error_msg
            return scraped_data

        query_encoded = quote_plus(query)
        url = f"https://www.bing.com/search?q={query_encoded}&form=QBLH"
        print(f"   Navigating (live) to: {url}")
        driver.set_page_load_timeout(WEBDRIVER_TIMEOUT)

        try:
            driver.get(url)
            print(f"   Page loaded: {driver.title}")
        except TimeoutException:
            print(f"   ⚠️ Timeout loading MAIN search page ({WEBDRIVER_TIMEOUT}s). Attempting to proceed.", file=sys.stderr)
        except WebDriverException as e_nav:
             error_msg = f"WebDriver error during navigation to {url}: {e_nav}"
             print(f"   ❌ {error_msg}", file=sys.stderr)
             scraped_data["error"] = error_msg
             if driver:
                 try: driver.quit()
                 except Exception as e_quit: print(f"   ⚠️ Error quitting WebDriver after nav error: {e_quit}", file=sys.stderr)
             return scraped_data

        wait = WebDriverWait(driver, WEBDRIVER_TIMEOUT)
        results_locator = (By.ID, "b_results")
        try:
            print(f"   Waiting for search results ({results_locator})...")
            wait.until(EC.presence_of_element_located(results_locator))
            print("   ✅ Search results container found.")
        except TimeoutException:
            print(f"   ⚠️ Timeout waiting for main search results container ({results_locator}, {WEBDRIVER_TIMEOUT}s). Scraping available.", file=sys.stderr)

        print("   Scraping main search results page (live)...")
        main_page_content = ""
        try:
            main_page_content = driver.page_source
            soup_main = BeautifulSoup(main_page_content, "lxml")
            selectors_to_remove = [
                "script", "style", "noscript", "header", "footer", "nav", "form",
                "aside", "button", "input", "textarea", "iframe",
                ".b_scopebar", "#b_header", "#b_footer", "[role='navigation']",
                "[role='search']", "[role='banner']", "[role='complementary']",
                "[role='contentinfo']", ".sidebar", ".related-posts", ".comments",
                "[data-hveid]", "[jsaction]", ".ad_container"
            ]
            for selector in selectors_to_remove:
                try:
                    for element in soup_main.select(selector): element.decompose()
                except Exception as e_decompose: print(f"     ⚠️ Minor error decomposing '{selector}': {e_decompose}", file=sys.stderr)

            main_page_text = soup_main.get_text(separator="\n", strip=True)
            main_page_text = re.sub(r'\n\s*\n', '\n', main_page_text)
            if main_page_text:
                max_main_page_chars = 5000
                scraped_data["Bing Search Results Page"] = main_page_text[:max_main_page_chars]
                print(f"   ✅ Scraped main page text ({len(main_page_text)} chars, truncated to {max_main_page_chars}).")
                main_page_scraped = True
            else:
                print("   ⚠️ No text extracted from main search page after filtering.")
                scraped_data["Bing Search Results Page"] = "[No relevant text found on main search page]"

        except Exception as e_parse_main:
            print(f"   ❌ Error parsing main page source: {e_parse_main}", file=sys.stderr)
            scraped_data["Bing Search Results Page"] = f"[Error parsing main page: {e_parse_main}]"
            main_page_scraped = False

        print("   Extracting top result links (live)...")

        
        main_results_links = []
        try:
            link_elements = soup_main.select("li.b_algo h2 a[href]")
            for a_tag in link_elements:
                 title = a_tag.get_text(strip=True)
                 link = a_tag.get("href")
                 if link and title and link.startswith(('http://', 'https://')) and '#' not in link and 'microsoft' not in link and 'bing' not in link:
                      main_results_links.append({"text": title, "link": link})
                 if len(main_results_links) >= 3: break
            print(f"   Found {len(main_results_links)} valid result links to visit.")
        except Exception as e_link_extract:
            print(f"   ❌ Error extracting links from main page: {e_link_extract}", file=sys.stderr)

        links_to_visit = main_results_links
        print(f"   Visiting top {len(links_to_visit)} links with {LINK_LOAD_TIMEOUT}s timeout each.")
        body_locator = (By.TAG_NAME, "body")

        for i, item in enumerate(links_to_visit):
            link_url = item["link"]; link_title = item['text']
            source_key = f"Source [{i+1}]: {link_url} (Title: {link_title})"
            print(f"   🔗 Visiting link {i+1}/{len(links_to_visit)}: {link_url}")
            try:
                driver.set_page_load_timeout(LINK_LOAD_TIMEOUT)
                print(f"      Navigating (timeout: {LINK_LOAD_TIMEOUT}s)...")
                driver.get(link_url)
                print(f"      Page loaded: {driver.title}")
                try:
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located(body_locator))
                    print(f"      Body tag found.")
                except TimeoutException:
                    print(f"      ⚠️ Body tag not found quickly, proceeding anyway.", file=sys.stderr)

                print(f"      Scraping content from '{link_title}'...")
                link_page_source = driver.page_source
                soup_link = BeautifulSoup(link_page_source, "lxml")
                for selector in selectors_to_remove:
                     try:
                         for element in soup_link.select(selector): element.decompose()
                     except Exception as e_decompose_link: print(f"     ⚠️ Minor error decomposing '{selector}' on link page: {e_decompose_link}", file=sys.stderr)

                page_text = ""
                main_content_selectors = ["main","article","[role='main']","#main","#content",".main-content",".post-content",".entry-content",".article-body",".content"]
                found_main_content = False
                for selector in main_content_selectors:
                    main_element = soup_link.select_one(selector)
                    if main_element:
                        print(f"      Found main content area using selector: '{selector}'")
                        page_text = main_element.get_text(separator="\n", strip=True)
                        found_main_content = True
                        break
                if not found_main_content and soup_link.body:
                    print("      No specific main content found, falling back to body text.")
                    page_text = soup_link.body.get_text(separator="\n", strip=True)
                elif not found_main_content:
                     print("      ⚠️ No main content selectors matched and no body tag found.")
                     page_text = ""

                page_text = re.sub(r'\n\s*\n', '\n', page_text)
                max_link_chars = 4000
                page_text = page_text[:max_link_chars]

                if page_text:
                    scraped_data[source_key] = page_text
                    print(f"      ✅ Scraped link {i+1} ({len(page_text)} chars).")
                    links_scraped_count += 1
                else:
                    print(f"      ⚠️ No text scraped from link {i+1} after filtering.")
                    scraped_data[source_key] = "[No relevant text found on page]"

            except TimeoutException:
                print(f"      ❌ Timeout loading link {i+1} ({link_url}, {LINK_LOAD_TIMEOUT}s).", file=sys.stderr)
                scraped_data[source_key] = f"[Timeout Error loading page: {LINK_LOAD_TIMEOUT}s]"
                continue
            except WebDriverException as e_wd_link:
                print(f"      ❌ WebDriver error processing link {i+1} ({link_url}): {e_wd_link}", file=sys.stderr)
                scraped_data[source_key] = f"[WebDriver Error: {e_wd_link}]"
                continue
            except Exception as e_link:
                print(f"      ❌ Unexpected error processing link {i+1} ({link_url}): {type(e).__name__} - {e_link}", file=sys.stderr)
                scraped_data[source_key] = f"[Processing Error: {e_link}]"
                continue

    except Exception as e_main:
        error_msg = f"Major error during web search execution: {type(e_main).__name__} - {e_main}"
        print(f"❌ {error_msg}", file=sys.stderr)
        scraped_data["error"] = error_msg
    finally:
        if driver:
            print("   Attempting to quit WebDriver (live)...")
            try:
                driver.quit()
                print("   ✅ WebDriver quit successfully (live).")
            except Exception as e_quit:
                print(f"   ⚠️ Error quitting WebDriver: {e_quit}", file=sys.stderr)

    print(f"[_perform_web_search_and_extract] Finished search. Main page scraped: {main_page_scraped}. Links successfully scraped: {links_scraped_count}.")
    if not isinstance(scraped_data, dict): scraped_data = {"error": "Tool failed, non-dict result.", "_cache_status": "Live Search Failed (Internal Error)"}
    if not scraped_data: scraped_data = {"error": "Scraping failed to produce any data.", "_cache_status": "Live Search Failed"}
    return scraped_data


# --- Caching Wrapper Function (get_search_results_with_cache) ---
# --- [ Keep this function exactly as it was ] ---
def get_search_results_with_cache(query: str) -> dict:
    """Checks semantic cache using FAISS. If miss, performs live search and caches."""
    global faiss_index, index_id_to_data, next_faiss_id # Uses global cache variables

    print(f"\n[get_search_results_with_cache] Received query: '{query}'")
    if not query or not isinstance(query, str):
        print("   ⚠️ Invalid query received. Returning error.", file=sys.stderr)
        return {"error": "Invalid or empty query received.", "_cache_status": "Error"}
    query = query.strip()
    if not query:
         print("   ⚠️ Empty query after stripping. Returning error.", file=sys.stderr)
         return {"error": "Empty query received.", "_cache_status": "Error"}

    if faiss_index is None:
        print("   ⚠️ FAISS index (global) not initialized! Cannot use cache. Live search ONLY.", file=sys.stderr)
        live_data = _perform_web_search_and_extract(query)
        live_data["_cache_status"] = "Live Search (FAISS Not Init)"
        return live_data

    print(f"   Generating embedding for query: '{query[:100]}...'")
    new_query_vector = get_embedding(query, task_type="RETRIEVAL_QUERY") # Uses global client

    if new_query_vector is None:
        print("   ⚠️ Embedding failed. Skipping cache lookup. Performing live search.")
        live_data = _perform_web_search_and_extract(query)
        live_data["_cache_status"] = "Live Search (Embedding Failed)"
        return live_data

    try:
        faiss.normalize_L2(new_query_vector.reshape(1, -1))
    except Exception as e_norm:
         print(f"   ⚠️ Error normalizing query vector: {e_norm}. Skipping cache. Live search.", file=sys.stderr)
         live_data = _perform_web_search_and_extract(query)
         live_data["_cache_status"] = "Live Search (Vector Norm Failed)"
         return live_data

    cache_hit = False
    cached_data = None
    best_match_score = -1.0

    if faiss_index.ntotal > 0:
        try:
            print(f"   Searching FAISS index ({faiss_index.ntotal} vectors)...")
            D, I = faiss_index.search(new_query_vector.reshape(1, -1), 1)

            if I.size > 0 and D.size > 0:
                nearest_neighbor_id = int(I[0][0])
                similarity_score = float(D[0][0])
                best_match_score = similarity_score
                print(f"   FAISS NN ID: {nearest_neighbor_id}, Similarity Score: {similarity_score:.4f}")

                if similarity_score >= CACHE_SIMILARITY_THRESHOLD:
                    print(f"   Similarity score meets threshold {CACHE_SIMILARITY_THRESHOLD}.")
                    # Check mapping using int key
                    if nearest_neighbor_id in index_id_to_data:
                        cached_query_str, cached_filepath = index_id_to_data[nearest_neighbor_id]
                        print(f"   Found mapping: Original='{cached_query_str}', File='{cached_filepath}'")
                        if os.path.exists(cached_filepath):
                            print(f"   ✅ FAISS Cache HIT! Reading data from {cached_filepath}")
                            try:
                                with open(cached_filepath, 'r', encoding='utf-8') as f:
                                    cached_data = json.load(f)
                                # Clean up internal fields before returning
                                cached_data.pop('_cached_original_query', None)
                                cached_data.pop('_cache_timestamp', None)
                                cached_data['_cache_status'] = f'HIT (Similarity: {similarity_score:.4f})'
                                cache_hit = True
                            except Exception as e_read:
                                print(f"   ⚠️ Error reading/parsing cache file {cached_filepath}: {e_read}. Invalidating. Live search.", file=sys.stderr)
                        else:
                            print(f"   ⚠️ Cache file missing: {cached_filepath}. Invalidating. Live search.", file=sys.stderr)
                            try: del index_id_to_data[nearest_neighbor_id]; print(f"   Removed inconsistent mapping (ID: {nearest_neighbor_id}).")
                            except Exception as e_del: print(f"   ⚠️ Error removing inconsistent mapping: {e_del}", file=sys.stderr)
                    else:
                        print(f"   ⚠️ FAISS ID {nearest_neighbor_id} not in mapping. Cache inconsistent. Live search.", file=sys.stderr)
                else:
                    print(f"   Similarity score below threshold. Cache MISS.")
            else:
                print("   FAISS search returned empty results. Cache MISS.")
        except Exception as e_search:
            print(f"   ⚠️ Error during FAISS search: {type(e_search).__name__} - {e_search}. Live search.", file=sys.stderr)
    else:
        print("   FAISS index is empty. Live search.")

    if cache_hit and cached_data is not None:
        print("[get_search_results_with_cache] Returning cached result.")
        return cached_data
    else:
        print(f"[get_search_results_with_cache] Cache MISS or error. Performing live search. (Best score: {best_match_score:.4f})")
        live_data = _perform_web_search_and_extract(query)

        # Cache successful live results
        if isinstance(live_data, dict) and "error" not in live_data and live_data:
            query_hash = normalize_query_for_filename(query)
            cache_filepath = os.path.join(CACHE_DIR, f"{query_hash}.json")
            try:
                live_data_to_save = live_data.copy()
                live_data_to_save['_cached_original_query'] = query
                live_data_to_save['_cache_timestamp'] = time.time()

                print(f"   Attempting to save successful live results to cache file: {cache_filepath}")
                with open(cache_filepath, 'w', encoding='utf-8') as f:
                    json.dump(live_data_to_save, f, indent=2, ensure_ascii=False)
                print(f"   ✅ Live data saved to cache file.")

                # Add to FAISS
                if new_query_vector is not None:
                    current_id = next_faiss_id
                    print(f"   Adding vector to FAISS index (ID: {current_id})...")
                    faiss_index.add(new_query_vector.reshape(1, -1))
                    print(f"   Adding mapping to index_id_to_data (ID: {current_id})...")
                    index_id_to_data[current_id] = [query, cache_filepath] # Use int key
                    next_faiss_id += 1
                    print(f"   FAISS index size: {faiss_index.ntotal}. Mapping size: {len(index_id_to_data)}. Next ID: {next_faiss_id}")
                    save_faiss_cache() # Save updates
                else:
                    print("   ⚠️ Skipping FAISS index update: embedding vector missing.")
            except Exception as e_save:
                print(f"   ⚠️ Error saving results/updating FAISS: {type(e_save).__name__} - {e_save}", file=sys.stderr)
                live_data["_cache_status"] = "Live Search (Cache Save Failed)"
        elif isinstance(live_data, dict) and "error" in live_data:
             live_data["_cache_status"] = f"Live Search Failed ({live_data.get('error', 'Unknown error')})"
             print(f"   Live search failed, not caching. Error: {live_data.get('error')}")
        else:
             print(f"   Live search returned unexpected/empty data: {type(live_data)}. Not caching.")
             if not isinstance(live_data, dict): live_data = {"error": "Live search returned non-dict data.", "_cache_status": "Live Search Failed (Internal Error)"}
             elif not live_data: live_data = {"error": "Live search returned empty results.", "_cache_status": "Live Search Failed (Empty)"}

        # Ensure status is set correctly
        if isinstance(live_data, dict) and "_cache_status" not in live_data:
             live_data["_cache_status"] = "Live Search (Cache Miss)"

        # Clean up internal fields before final return
        if isinstance(live_data, dict):
            live_data.pop('_cached_original_query', None)
            live_data.pop('_cache_timestamp', None)

        print("[get_search_results_with_cache] Returning live search result.")
        return live_data


# --- Tool and Instruction Definition Functions ---
def get_tools():
    """Returns the list of tools (functions) available to the Gemini model."""
    print("Defining Tool List (Web Search with Cache)...")
    sports_tools = [get_search_results_with_cache]
    print(f"✅ Tools defined: {[func.__name__ for func in sports_tools]}")
    return sports_tools

def get_system_instruction():
    """Returns the system instruction string for the Gemini model."""
    # --- [ Keep the FULL System Instruction Text Here ] ---
    return """You are a specialized Sports Information Chatbot. Your primary goal is to provide accurate and relevant answers to user questions about sports using your internal knowledge FIRST. You also have a web search tool (`get_search_results_with_cache`) as a backup.

**Decision Process:**
1.  **Analyze the Query:** Understand the user's question, intent, timeframe, and desired output (e.g., fact, score, stats, *text* commentary).
2.  **Attempt Internal Answer First:** Check internal knowledge thoroughly for rules, history (like IPL 2014 winner), players, concepts, even scorecards if known reliably. If confident, provide the answer directly.
3.  **Identify Need for Web Search Tool:** Use `get_search_results_with_cache` tool ONLY if:
    *   **(A) Live/Very Recent Info Needed:** User asks for info (scores, results, *text* commentary/play-by-play) about games **RIGHT NOW** or **last ~3 days**.
    *   **(B) Internal Knowledge Lacking:** You cannot confidently answer a query about specific/obscure stats, records, less common historical facts, or *detailed text commentary/play-by-play* internally.
    *   **(C) Explicit Commentary Request:** User asks for "commentary", "play-by-play", or to "describe" a specific event/moment in detail. Use the tool to find textual descriptions or live text commentary feeds.
4.  **Formulate Search Query (If Tool Used):** Create a concise query.
    *   For facts/scores/stats: Target that info (e.g., "Man City match result yesterday"). Use history for context (e.g., "IPL score yesterday").
    *   **For Commentary Requests:** Target *text commentary* or *play-by-play descriptions* (e.g., "live text commentary IND vs AUS cricket", "play by play description Messi goal final", "detailed description last over 2014 ipl final").
    **IMPORTANT: Directly initiate the tool call process.**
5.  **Synthesize Tool Results:** The tool returns a dictionary of text snippets. Examine ALL text.
    *   **For Factual Queries:** Extract specific info accurately.
    *   **For Commentary Requests:** Find relevant descriptions or play-by-play text. **Synthesize this text into an engaging, commentary-style response.** Rephrase the factual information to sound like a commentator describing the action. Do NOT just copy text.
    *   **If Info Missing:** If the specific detail (or commentary text) isn't found, state that.
6.  **Handle Tool Failure:** If the tool returns an 'error' key, inform the user the search failed.

**Core Principle:** Internal knowledge first. Web search tool for live/recent info, when knowledge is lacking, OR for finding text to synthesize commentary from.
"""

# --- Initialization Function (Cached) ---
@st.cache_resource
def initialize_chatbot_resources():
    """
    Initializes the Gemini client and loads FAISS cache.
    Called once by Streamlit. Returns the necessary objects.
    Uses genai.Client() based on user's original script.
    """
    st.status("Initializing chatbot resources (Client & FAISS Cache)...", expanded=False)
    print("--- Running initialize_chatbot_resources() ---")
    # Needs API key from secrets
    _api_key = st.secrets.get("GOOGLE_API_KEY")
    if not _api_key:
        st.error("API Key not found in secrets during resource initialization!")
        print("❌ ERROR: API Key missing in initialize_chatbot_resources", file=sys.stderr)
        st.stop()

    try:
        # 1. Initialize Gemini Client using genai.Client()
        print("   Initializing Gemini Client using genai.Client()...")
        # Pass the retrieved API key here
        _gemini_client = genai.Client(api_key=_api_key)
        print("   ✅ Gemini Client initialized.")

        # 2. Load FAISS cache
        print("   Loading FAISS cache...")
        _faiss_index, _index_id_to_data, _next_faiss_id = load_faiss_cache()
        print("   ✅ FAISS Cache loaded/initialized.")

        # 3. Return the initialized objects
        print("--- Initialization complete ---")
        return _gemini_client, _faiss_index, _index_id_to_data, _next_faiss_id
    except Exception as e:
        st.error(f"Fatal Error during resource initialization: {e}")
        print(f"❌ FATAL ERROR during initialize_chatbot_resources: {type(e).__name__} - {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        st.stop()

# --- Run Initialization and Assign Globals ---
try:
    print("Assigning initialized resources to global scope...")
    # Call the cached function to get/create the resources
    # This now returns the client object created with genai.Client()
    initialized_client, initialized_faiss_index, initialized_index_id_to_data, initialized_next_faiss_id = initialize_chatbot_resources()

    # Assign the returned objects to the global variables
    client = initialized_client # Assign the client object globally
    faiss_index = initialized_faiss_index
    index_id_to_data = initialized_index_id_to_data
    next_faiss_id = initialized_next_faiss_id

    if client is None or faiss_index is None:
         print("⚠️ WARNING: Globals (client or faiss_index) are still None after assignment!", file=sys.stderr)
         st.warning("Initialization issue detected. Bot may not function correctly.")
    else:
         print(f"✅ Globals assigned. Client Type: {type(client)}, FAISS Index Items: {faiss_index.ntotal}")

except Exception as e:
    st.error(f"Error during resource assignment: {e}")
    print(f"❌ ERROR assigning initialized resources: {e}", file=sys.stderr)
    st.stop()

# --- Get Tools and System Instruction ---
try:
    SPORTS_TOOLS = get_tools()
    SYSTEM_INSTRUCTION = get_system_instruction()
    if not SPORTS_TOOLS or not SYSTEM_INSTRUCTION:
        raise ValueError("Failed to retrieve tools or system instruction.")
    print("✅ Tools and System Instruction retrieved.")
except Exception as e:
    st.error(f"Error getting tools or system instruction: {e}")
    print(f"❌ ERROR getting tools/system instruction: {e}", file=sys.stderr)
    st.stop()

# --- Chat Session Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    print("Initialized new chat history in session state.")

# Initialize the Gemini Chat object if it doesn't exist
# Uses the client.chats.create() method as per original script
if "chat" not in st.session_state:
    try:
        print(f"\nCreating NEW Gemini Chat Session with model '{MODEL_NAME}' using client.chats.create()...")
        # Ensure the global client is initialized and assigned
        if client is None:
            raise ValueError("Gemini client (global) is not initialized before creating chat.")

        # *** Use client.chats.create() ***
        st.session_state.chat = client.chats.create(
            model=MODEL_NAME,
            config=genai_types.GenerateContentConfig( # Use imported types
                system_instruction=SYSTEM_INSTRUCTION,
                tools=SPORTS_TOOLS,
            )
        )
        print("✅ New Gemini chat session created via client.chats.create() and stored.")
    except Exception as e:
        st.error(f"❌ ERROR: Failed to initialize Gemini chat session: {type(e).__name__} - {e}")
        print(f"❌ ERROR: Failed to initialize chat session: {type(e).__name__} - {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        st.stop()

# --- UI Display ---
st.title("🏆 Sports Chatbot ⚽")
st.caption(f"Powered by Google Gemini ({MODEL_NAME}) with Web Search & FAISS Semantic Cache")
st.markdown("---")

# Display past chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- User Input and Chat Logic ---
if prompt := st.chat_input("Ask me about sports scores, stats, rules, or commentary..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response_content = ""
        error_occurred = False

        try:
            print(f"\n👤 User Query: {prompt}")
            print("🤖 Assistant Thinking...")
            with st.spinner("Thinking... (May perform web search)"):
                # *** Send message using the chat object created by client.chats.create() ***
                # This object should handle automatic function calling if configured correctly
                response = st.session_state.chat.send_message(prompt)

                # --- [ Keep the response handling logic exactly the same ] ---
                if response.text:
                    full_response_content = response.text
                    print(f"✅ Received response text: {full_response_content[:200]}...")
                elif response.candidates:
                     candidate = response.candidates[0]
                     finish_reason = "UNKNOWN"
                     if candidate.finish_reason and hasattr(candidate.finish_reason, 'name'):
                          finish_reason = candidate.finish_reason.name
                     print(f"⚠️ Received candidate with finish_reason: {finish_reason} but no direct text.")
                     if finish_reason == "STOP" and not candidate.content.parts: full_response_content = "(Model finished but no text response.)"
                     elif finish_reason == "TOOL_CALLS": full_response_content = "(Tool processing issue.)"; print(f"DEBUG: Final state TOOL_CALLS")
                     elif finish_reason == "SAFETY": full_response_content = "⚠️ Response blocked (safety)."; st.warning(full_response_content)
                     elif finish_reason == "MAX_TOKENS": full_response_content = "⚠️ Response truncated (length)."; st.warning(full_response_content)
                     else: full_response_content = f"(Finished: {finish_reason}, no text.)"
                else:
                    full_response_content = "(Received empty/unexpected response.)"
                    print("⚠️ Received empty/unexpected response object.")

        except StopCandidateException as e:
            error_occurred = True
            finish_reason_name = e.finish_reason.name if hasattr(e, 'finish_reason') else "UNKNOWN"
            st.error(f"⚠️ Response stopped: **{finish_reason_name}**")
            full_response_content = f"Response generation stopped ({finish_reason_name})."
            print(f"⚠️ StopCandidateException: {finish_reason_name}", file=sys.stderr)
            if finish_reason_name == "SAFETY": st.warning("Content may be blocked (safety).")
            elif finish_reason_name == "MAX_TOKENS": st.warning("Response may be incomplete (length).")

        except Exception as e:
            error_occurred = True
            st.error(f"❌ Unexpected error: {type(e).__name__}")
            full_response_content = f"Sorry, technical issue. Try again.\n\n*Error logged.*"
            print(f"❌ Chat Error: {type(e).__name__} - {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

        message_placeholder.markdown(full_response_content)

    st.session_state.messages.append({"role": "assistant", "content": full_response_content})

# --- Sidebar ---
# --- [ Keep the Sidebar code exactly the same ] ---
with st.sidebar:
    st.header("⚙️ Bot Info & Settings")
    st.markdown("---")
    st.write(f"**Model:** `{MODEL_NAME}`")
    st.write(f"**Embedding:** `{EMBEDDING_MODEL}`")
    st.markdown("---")
    st.subheader("Cache Details")
    st.write(f"**Status:** {'Loaded' if faiss_index is not None else 'Not Loaded'}")
    if faiss_index is not None: st.write(f"**Items Indexed:** `{faiss_index.ntotal}`")
    else: st.write("**Items Indexed:** `N/A`")
    st.write(f"**Directory:** `{os.path.abspath(CACHE_DIR)}`")
    st.write(f"**Similarity Threshold:** `{CACHE_SIMILARITY_THRESHOLD}`")
    st.markdown("---")
    st.header("📄 Session Control")
    if st.button("Clear Chat History", key="clear_chat"):
        st.session_state.messages = []
        if "chat" in st.session_state: del st.session_state["chat"]
        print("Chat history and session object cleared.")
        st.rerun()
    st.caption("Reload page to fully reset.")
