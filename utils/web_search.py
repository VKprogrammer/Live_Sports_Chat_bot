import os
import sys
import re
import traceback
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import json
import hashlib
from config import WEBDRIVER_TIMEOUT, LINK_LOAD_TIMEOUT, CHROMEDRIVER_PATH, CACHE_DIR

def normalize_query_for_filename(query: str) -> str:
    """Creates a safe filename hash from a query."""
    return hashlib.sha1(query.encode('utf-8')).hexdigest()

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

def get_search_results_with_cache(query: str) -> dict:
    """Checks semantic cache using FAISS. If miss, performs live search and caches."""
    # Import here to avoid circular imports
    from utils.cache_utils import get_from_cache, add_to_cache
    from utils.embedding_utils import get_embedding
    
    print(f"\n[get_search_results_with_cache] Received query: '{query}'")
    if not query or not isinstance(query, str):
        print("   ⚠️ Invalid query received. Returning error.", file=sys.stderr)
        return {"error": "Invalid or empty query received.", "_cache_status": "Error"}
    
    query = query.strip()
    if not query:
         print("   ⚠️ Empty query after stripping. Returning error.", file=sys.stderr)
         return {"error": "Empty query received.", "_cache_status": "Error"}

    # Generate embedding for the query
    query_vector = get_embedding(query, task_type="RETRIEVAL_QUERY")
    if query_vector is None:
        print("   ⚠️ Embedding failed. Skipping cache lookup. Performing live search.")
        live_data = _perform_web_search_and_extract(query)
        live_data["_cache_status"] = "Live Search (Embedding Failed)"
        return live_data

    # Try to get from cache
    cached_data, similarity_score = get_from_cache(query, query_vector)
    if cached_data is not None:
        print(f"[get_search_results_with_cache] Cache HIT with similarity {similarity_score:.4f}. Returning cached result.")
        return cached_data

    # Cache miss, perform live search
    print(f"[get_search_results_with_cache] Cache MISS. Performing live search.")
    live_data = _perform_web_search_and_extract(query)
    
    # Cache the result if it's valid
    if isinstance(live_data, dict) and "error" not in live_data and live_data:
        add_to_cache(query, query_vector, live_data)
        live_data["_cache_status"] = "Live Search (Cache Miss)"
    elif isinstance(live_data, dict) and "error" in live_data:
        live_data["_cache_status"] = f"Live Search Failed ({live_data.get('error', 'Unknown error')})"
    else:
        if not isinstance(live_data, dict): 
            live_data = {"error": "Live search returned non-dict data.", "_cache_status": "Live Search Failed (Internal Error)"}
        elif not live_data: 
            live_data = {"error": "Live search returned empty results.", "_cache_status": "Live Search Failed (Empty)"}
    
    print("[get_search_results_with_cache] Returning live search result.")
    return live_data
