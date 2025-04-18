# Streamlit Sports Chatbot with Gemini, Selenium & FAISS Cache


## Overview

This project implements an interactive **Sports Information Chatbot** using Python and Streamlit. It leverages the power of Google's **Gemini large language model (`gemini-2.0-flash`)** to understand user queries and generate informative responses about various sports topics, including rules, history, player stats, and more.

For up-to-date information like live scores or recent commentary, it employs **Selenium** for web scraping. To optimize performance and reduce redundant searches, results are cached using a **FAISS**-based semantic cache powered by Google's embedding models.

The primary goal is to provide accurate sports information, prioritizing the model's internal knowledge and resorting to live web data only when necessary (e.g., for very recent events or specific commentary requests).

## Features

*   **Conversational AI:** Utilizes Google Gemini (`gemini-2.0-flash`) for natural language understanding and response generation regarding sports rules, history, players, stats, etc.
*   **Live Web Search:** Integrates a tool using **Selenium** and **BeautifulSoup4** to scrape Bing search results and linked pages. This is crucial for:
    *   Fetching live scores or results from the last ~3 days.
    *   Finding specific textual **commentary** or play-by-play descriptions when requested.
*   **Semantic Caching:** Implements a robust caching layer to minimize redundant web searches and API calls:
    *   Uses Google's `embedding-001` model to create vector embeddings of search queries.
    *   Stores embeddings and references to cached results in a **FAISS** index (`faiss-cpu`) for efficient similarity searching.
    *   If a similar query is found above a defined threshold (`CACHE_SIMILARITY_THRESHOLD`), cached results are served instantly.
    *   Raw scraped data is stored locally in JSON files within the cache directory (`search_cache_v6_text_commentary/`).
*   **Streamlit User Interface:** Provides a clean, interactive chat interface built with Streamlit for easy user interaction.
*   **Tool-Augmented Generation:** Follows a pattern where the LLM can decide to use external tools (the web search cache function) to augment its knowledge based on the query and system instructions.
*   **Standardized Secret Management:** Uses the `.streamlit/secrets.toml` file for API key configuration across different environments (local, Codespaces).

## Technology Stack

*   **Frontend:** Streamlit
*   **LLM:** Google Gemini (`gemini-2.0-flash` via `google-generativeai` SDK)
*   **Embeddings:** Google Embedding Model (`embedding-001`)
*   **Web Scraping:** Selenium, BeautifulSoup4, lxml
*   **Vector Search/Caching:** FAISS (`faiss-cpu`), NumPy
*   **Configuration:** `.streamlit/secrets.toml`
*   **Core:** Python 3.9+

## Prerequisites

Before you begin, ensure you have the following installed and configured:

1.  **Python:** Version 3.9 or higher recommended. Check with `python --version`.
2.  **Git:** For cloning the repository. Check with `git --version`.
3.  **Visual Studio Code (Recommended):** Used in the setup instructions, but other editors are possible.
4.  **VS Code Python Extension:** Install from the VS Code Marketplace if using VS Code.
5.  **Google API Key:** An active API key for Google AI Studio (Gemini).
    *   Obtain from [Google AI Studio](https://aistudio.google.com/).
    *   **Keep this key secure and do not commit it to version control!**
6.  **Google Chrome Browser:** Required by Selenium for automation. Ensure it's installed.
7.  **ChromeDriver:** The WebDriver executable that **exactly matches** your installed Chrome version.
    *   Check Your Chrome Version: In Chrome, go to `chrome://settings/help`. Note the full version number (e.g., 114.0.5735.199).
    *   Download ChromeDriver: Go to the [Chrome for Testing availability dashboard](https://googlechromelabs.github.io/chrome-for-testing/). Find the version matching your Chrome browser and download the `chromedriver` binary for your operating system (e.g., `chromedriver-win64.zip`, `chromedriver-mac-x64.zip`, `chromedriver-linux64.zip`). Unzip the file if necessary.
    *   **Placement (Choose ONE):**
        *   **(Recommended for Simplicity): Add to PATH:** Add the *directory* containing the extracted `chromedriver` executable to your system's **PATH** environment variable. This allows the script (`app.py` with `CHROMEDRIVER_PATH = None`) to find it automatically.
        *   **(Alternative): Set Script Variable:** Modify the `CHROMEDRIVER_PATH` variable near the top of `app.py` to the *full, absolute path* of the `chromedriver` executable itself (e.g., `CHROMEDRIVER_PATH = "/Users/you/drivers/chromedriver"` or `CHROMEDRIVER_PATH = "C:\\webdrivers\\chromedriver.exe"`).

## Setup and Running

You can set up and run this project using two primary methods:

1.  **GitHub Codespaces:** A cloud-based development environment accessible directly from your browser.
2.  **Local Setup using VS Code:** Requires manual installation of prerequisites on your own machine.

**Both methods require configuring the Google API key using a `.streamlit/secrets.toml` file.**

---

### Method 1: GitHub Codespaces

GitHub Codespaces provides a complete, configurable development environment in the cloud, including a VS Code-like editor and terminal.

1.  **Navigate to the Repository:** Go to the main page of this repository on GitHub.
2.  **Launch Codespace:**
    *   Click the green `<> Code` button.
    *   Go to the `Codespaces` tab.
    *   Click `Create codespace on main` (or your desired branch). GitHub will set up the environment (this might take a minute or two).
3.  **Environment Ready:** Once loaded, you'll have a VS Code interface running in your browser, connected to a cloud container with your code checked out.
4.  **Open Terminal:** Use the integrated terminal within the Codespace (Menu -> Terminal -> New Terminal, or `Ctrl+` / `Cmd+`).
5.  **Install Dependencies:** Ensure Python packages are installed from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```
6.  **Configure API Key (`secrets.toml`):**
    *   **Create the Directory:** In the Codespace terminal, create the required directory:
        ```bash
        mkdir .streamlit
        ```
    *   **Create the File:** Create the secrets file:
        ```bash
        touch .streamlit/secrets.toml
        ```
    *   **Edit the File:** Open the `secrets.toml` file using the Codespace file explorer (usually on the left sidebar). Navigate into the `.streamlit` directory, then click on `secrets.toml` to open it in the editor tab.
    *   **Add Your Key:** Paste the following line into the `secrets.toml` editor tab, replacing the placeholder with your **actual** Google API Key:
        ```toml
        # .streamlit/secrets.toml
        GOOGLE_API_KEY = "API_KEY" # <-- Replace with YOUR ACTUAL KEY
        ```
    *   **Save the file** (File -> Save, or `Ctrl+S` / `Cmd+S`).
7.  **ChromeDriver Check:** Codespaces environments (like the default Python/Debian images) often come with compatible versions of Chrome and ChromeDriver pre-installed and configured in the PATH. The default setting `CHROMEDRIVER_PATH = None` in `app.py` should generally work without changes here.
8.  **Run the Application:** In the Codespace terminal:
    ```bash
    streamlit run app.py
    ```
9.  **Access the App:** Codespaces automatically detects the running Streamlit application and forwards the port (usually 8501). A notification should appear in the bottom-right corner of VS Code with a button like "Open in Browser". Click this button to access your running chatbot.

---

### Method 2: Local Setup using VS Code

This method requires setting up the environment directly on your computer.

1.  **Prerequisites:** Ensure you have installed Python, Git, VS Code (with Python Extension), Google Chrome, and **configured ChromeDriver** correctly (either in PATH or via the `CHROMEDRIVER_PATH` variable in the script) as detailed in the main **Prerequisites** section above.

2.  **Clone Repository:** Open your local terminal or command prompt:
    ```bash
    git clone <your-repository-url>
    cd <repository-directory-name>
    ```

3.  **Open in VS Code:**
    ```bash
    code .
    ```

4.  **Create & Activate Virtual Environment:** (Highly Recommended)
    Open the VS Code integrated terminal (`Ctrl+` or `Cmd+`).
    ```bash
    # Create environment (using .venv is common)
    python -m venv .venv

    # Activate environment:
    # Windows (Git Bash/PowerShell):
    source .venv/Scripts/activate
    # macOS/Linux:
    source .venv/bin/activate
    ```
    Your terminal prompt should now be prefixed with `(.venv)`.

5.  **Select Python Interpreter (VS Code):**
    *   Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
    *   Type and select `Python: Select Interpreter`.
    *   Choose the Python interpreter located within your `.venv` directory (it might be marked 'Recommended' or list the `.venv` path).

6.  **Install Dependencies:** Ensure the virtual environment is active in your terminal.
    ```bash
    pip install -r requirements.txt
    ```

7.  **Configure API Key (`secrets.toml`):**
    *   **Create Directory:** In your project's root directory (using VS Code's Explorer or the terminal):
        ```bash
        mkdir .streamlit
        ```
    *   **Create File:** Inside the `.streamlit` directory, create the `secrets.toml` file (Right-click -> New File in VS Code Explorer, or `touch .streamlit/secrets.toml` in terminal).
    *   **Edit File:** Open `.streamlit/secrets.toml` in VS Code and add your Google API key, replacing the placeholder:
        ```toml
        # .streamlit/secrets.toml
        GOOGLE_API_KEY = "API_KEY" # <-- Replace with YOUR ACTUAL KEY
        ```
    *   **Save the file.**
    *   **IMPORTANT - Git Ignore:** Ensure your `.gitignore` file exists in the project root and contains a line to ignore the secrets directory:
        ```gitignore
        # .gitignore
        .venv/
        __pycache__/
        *.pyc
        *.pyo
        *.pyd
        .streamlit/  # CRITICAL: Prevents committing secrets
        search_cache_v6_text_commentary/
        *.DS_Store
        .env # If you ever use dotenv
        ```
        If `.gitignore` doesn't exist, create it and add these lines.

8.  **Run the Application:** In your terminal (ensure the `.venv` is still active):
    ```bash
    streamlit run app.py
    ```
9.  **Access the App:** Streamlit will typically output `Network URL` and `External URL` and automatically attempt to open the application in your default web browser at `http://localhost:8501`.

---

## How It Works (Simplified Flow)

1.  **User Input:** The user types a question into the Streamlit chat interface.
2.  **Initial LLM Check:** The query is sent to the Gemini model via the `google-generativeai` SDK. The model first attempts to answer using its internal knowledge based on the system instructions.
3.  **Tool Decision:** If the query requires recent information (live scores, commentary) or if the model lacks confidence, it may decide to call the `get_search_results_with_cache` tool.
4.  **Embedding & Cache Check:**
    *   An embedding vector is generated for the query using `embedding-001`.
    *   The FAISS index (`faiss_index_v6.idx`) is searched for similar query embeddings.
5.  **Cache Hit:** If a similar query is found above the threshold (`CACHE_SIMILARITY_THRESHOLD`), the corresponding cached JSON data (previously scraped results) is retrieved from the `search_cache_v6_text_commentary/` directory using the mapping in `faiss_mapping_v6.json`.
6.  **Cache Miss (Live Search):**
    *   If no suitable cache entry exists, the `_perform_web_search_and_extract` function is called.
    *   Selenium launches a headless Chrome instance, navigates to Bing, searches, and scrapes the results page.
    *   It then visits the top relevant links (avoiding certain domains), scraping their content using BeautifulSoup.
    *   The extracted text data is structured into a dictionary.
7.  **Cache Update:** If the live search was successful, the results dictionary is saved as a JSON file (named using a hash of the query), and the query embedding + file path are added to the FAISS index and mapping file. `faiss.write_index` saves the updated index.
8.  **Response Synthesis:** The Gemini model receives the information (either from internal knowledge, cached data, or fresh scraped data) and synthesizes the final response. For commentary requests using scraped data, it aims to rephrase the information in an engaging style based on the system prompt.
9.  **Display:** The final response is displayed in the Streamlit chat interface.

## Cache Management

*   All cache files related to web search results are stored in the `search_cache_v6_text_commentary/` directory within your project folder.
*   `faiss_index_v6.idx`: The FAISS index file containing query embeddings. This is a binary file.
*   `faiss_mapping_v6.json`: A JSON file mapping FAISS index IDs (integers) to the original query string and the path to the cached JSON result file. It also stores the `next_id` counter for the index.
*   `[hash].json`: Individual JSON files (named by a SHA1 hash of the original query) containing the structured scraped data (text snippets from Bing and linked pages) for each unique query performed live.
*   **Clearing the Cache:** To completely reset the web search cache (e.g., if it becomes corrupted or you want to force fresh searches), simply **delete the entire `search_cache_v6_text_commentary/` directory**. The application will automatically recreate it, along with the index and mapping files, the next time a web search is performed and cached.

## Troubleshooting

*   **`selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH...`** or similar `WebDriverException`:
    *   Verify your ChromeDriver version exactly matches your Chrome browser version.
    *   Confirm ChromeDriver is correctly placed in a directory listed in your system's PATH environment variable (and restart your terminal/VS Code after modifying PATH).
    *   Alternatively, double-check the absolute path set in the `CHROMEDRIVER_PATH` variable in `app.py` is correct.
    *   Ensure the `chromedriver` file has execute permissions (`chmod +x chromedriver` on Linux/macOS).
*   **`KeyError: 'GOOGLE_API_KEY'`** during startup or API calls:
    *   Ensure the `.streamlit/` directory exists in your project root.
    *   Ensure the `secrets.toml` file exists inside `.streamlit/`.
    *   Verify the key name inside `secrets.toml` is exactly `GOOGLE_API_KEY`.
    *   Confirm you have pasted your *actual* API key as the value within the quotes in `secrets.toml`.
    *   Make sure you saved the `secrets.toml` file after editing.
*   **`ModuleNotFoundError: No module named 'X'`**: A required Python package is missing.
    *   Ensure your virtual environment (`.venv`) is activated in the terminal where you are running `streamlit run`.
    *   Run `pip install -r requirements.txt` again within the activated environment.
*   **Selenium Errors during Scraping (Timeout, Element Not Found, etc.):**
    *   Web scraping is inherently fragile. Bing or target websites might change their HTML structure, breaking the CSS selectors used in `_perform_web_search_and_extract`. The scraping logic might need updating.
    *   Websites may employ anti-scraping measures (CAPTCHAs, IP blocks). Running frequently might increase the chance of blocks.
    *   Check network connectivity. Increase timeouts (`WEBDRIVER_TIMEOUT`, `LINK_LOAD_TIMEOUT` in the script) if running on a slow connection, but this may not always help.
*   **High Resource Usage (RAM/CPU):**
    *   Running Selenium (a full browser instance) can be resource-intensive. Close unnecessary applications.
    *   FAISS indexing can also consume memory, especially with a large number of cached items.
*   **Cache Inconsistency Errors (FAISS size mismatch, ID not found):**
    *   If the application crashes or is stopped abruptly during a cache write operation, the index (`.idx`) and mapping (`.json`) files might become out of sync.
    *   The safest solution is usually to **delete the entire `search_cache_v6_text_commentary/` directory** and let the application rebuild the cache.

## Limitations & Known Issues

*   **Selenium Dependency:** The reliance on a local Chrome/ChromeDriver setup makes deploying this exact script to platforms without native browser environments (like the standard free tier of Streamlit Community Cloud) problematic without significant modification (e.g., switching to APIs).
*   **Scraping Fragility:** Web scraping logic is prone to breaking when website layouts or structures change. Maintenance may be required.
*   **Potential for Blocks:** Automated scraping can be detected and blocked by websites or search engines, potentially causing the web search tool to fail.
*   **Resource Intensive:** Selenium significantly increases RAM and CPU usage compared to API-based approaches.
*   **Cache Persistence (Deployment):** The file-based cache works well locally but is ephemeral on many cloud deployment platforms (like Streamlit Community Cloud free tier) where the filesystem is reset frequently. For persistent caching in the cloud, external storage (like S3/GCS with a cloud vector DB) would be needed.
*   **Accuracy:** The chatbot's accuracy depends on both the Gemini model's knowledge and the correctness/timeliness of the scraped web content. Scraped data might be inaccurate or biased.
*   **Commentary Synthesis:** The quality of synthesized commentary is highly dependent on finding relevant, descriptive text during web scraping. It might sometimes be generic or miss nuances if good source text isn't found.

## Future Improvements

*   **Replace Selenium with APIs:** Refactor the web search tool to use official Search Engine APIs (Google Custom Search API, Bing Search API) or robust third-party scraping APIs (SerpApi, ScraperAPI, etc.). This would improve reliability and deployment flexibility.
*   **Automated WebDriver Management:** Integrate the `webdriver-manager` Python library to automatically download and manage the correct ChromeDriver version, simplifying setup.
*   **Enhanced Error Handling:** Implement more specific error handling and user feedback during web scraping failures or API issues.
*   **Cache Invalidation Strategy:** Add logic to expire or refresh cached items, especially for time-sensitive queries (e.g., results older than X days).
*   **UI Enhancements:** Add features like displaying cache status (hit/miss), providing source URLs for information derived from web searches, or showing visual progress indicators during scraping.
*   **Cloud-Native Caching:** For cloud deployment, integrate with cloud storage (like AWS S3, Google Cloud Storage) and a cloud-based vector database (like Pinecone, Weaviate, Vertex AI Matching Engine) for persistent semantic caching.
*   **Asynchronous Operations:** Investigate using asynchronous libraries (`asyncio`, `httpx`) for potentially more efficient handling of web requests during scraping, although integration with Selenium can be complex.

## Contributing

Contributions, issues, and feature requests are welcome! Please feel free to open an issue or submit a pull request. (Consider adding more specific contribution guidelines if the project grows).

## License

