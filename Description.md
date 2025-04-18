# Project Description: Streamlit Sports Chatbot

## 1. Introduction

This document provides a detailed description of the Streamlit Sports Chatbot project. The goal is to create an interactive chatbot capable of answering sports-related questions, leveraging the strengths of a Large Language Model (LLM) combined with real-time web data acquisition and optimized retrieval through semantic caching.

The application uses Streamlit for the user interface, Google's Gemini (`gemini-2.0-flash`) as the core LLM, Selenium for web scraping, and FAISS for efficient semantic caching of web search results.

## 2. Core Workflow & Architecture

The application operates based on the following sequence of steps when a user submits a query:

1.  **User Input (Streamlit UI):**
    *   The user interacts with the chatbot via the Streamlit web interface (`st.chat_input`, `st.chat_message`).
    *   The user's query is captured and added to the session's message history (`st.session_state.messages`).

2.  **LLM Interaction (Gemini SDK):**
    *   The user's prompt is sent to the initialized Gemini chat session (`st.session_state.chat.send_message(prompt)`).
    *   This chat session (`client.chats.create`) was pre-configured with:
        *   The specific Gemini model (`MODEL_NAME`).
        *   A **System Instruction** (`SYSTEM_INSTRUCTION`) guiding the model's behavior and decision-making process.
        *   A list of available **Tools** (`SPORTS_TOOLS`), which currently includes the `get_search_results_with_cache` function.

3.  **Agent Decision-Making (Implicit via Gemini Tool Use):**
    *   Gemini processes the user query in the context of the chat history and the system instruction.
    *   **Internal Knowledge First:** Based on the system prompt, the model prioritizes answering using its internal knowledge base. If it can confidently answer questions about rules, established history, player facts, etc., it generates a direct text response.
    *   **Tool Trigger Evaluation:** The model evaluates if the query necessitates using the `get_search_results_with_cache` tool based on the criteria outlined in the system instruction:
        *   **Recency:** Is the query about live events, scores, or results within the last ~3 days?
        *   **Knowledge Gap:** Does the query ask for obscure stats, less common history, or specific details likely outside the model's training data?
        *   **Explicit Request Type:** Does the user specifically ask for "commentary," "play-by-play," or detailed descriptions of events?
    *   **Tool Call Initiation:** If the model determines a tool is needed, it doesn't generate text directly. Instead, it generates a specific `FunctionCall` structure, indicating the name of the tool (`get_search_results_with_cache`) and the arguments (the formulated search query string) it wants to use. The `google-generativeai` SDK handles this automatically when the chat session is configured with tools.

4.  **Tool Execution (`get_search_results_with_cache`):**
    *   The application framework intercepts the `FunctionCall` from Gemini.
    *   It executes the specified Python function: `get_search_results_with_cache(query=...)`.
    *   **Embedding & Cache Check:**
        *   An embedding vector for the search query is generated using the `embedding-001` model (`get_embedding` function).
        *   The FAISS index (`faiss_index`) is searched for embeddings similar to the query embedding using `faiss_index.search`.
        *   If a sufficiently similar vector is found (score >= `CACHE_SIMILARITY_THRESHOLD`), the corresponding cached result file path is retrieved from the mapping (`index_id_to_data`). The JSON data from this file is loaded. This constitutes a **Cache Hit**.
    *   **Live Web Search (Cache Miss):**
        *   If no suitable cache entry exists, the internal `_perform_web_search_and_extract` function is called.
        *   **Selenium Automation:** Launches a headless Chrome browser instance.
        *   **Bing Search:** Navigates to `bing.com` with the search query.
        *   **Page Parsing (BS4):** Parses the Bing results page HTML using BeautifulSoup to extract top result links and titles.
        *   **Link Visiting & Scraping:** Iterates through the top 3 relevant links:
            *   Navigates to each link using Selenium.
            *   Parses the linked page's HTML using BeautifulSoup.
            *   Applies selectors (`main`, `article`, etc.) to extract the main textual content, removing noise (scripts, ads, headers, footers).
            *   Truncates extracted text to manageable lengths.
        *   **Data Aggregation:** Collects the scraped text snippets into a dictionary, keyed by source (Bing page, Link 1 URL, Link 2 URL, etc.).
    *   **Cache Update:** If the live search was successful, the resulting dictionary is saved as a JSON file (hashed filename). The query embedding and file path are added to the FAISS index (`faiss_index.add`) and the ID-to-data mapping (`index_id_to_data`). The FAISS index is saved to disk (`faiss.write_index`).

5.  **Tool Result Submission:**
    *   The dictionary returned by `get_search_results_with_cache` (containing either cached data or fresh scraped data, along with a `_cache_status` field) is formatted as a `FunctionResponse`.
    *   This response is automatically sent back to the Gemini API by the SDK as the result of the function call it requested.

6.  **Final Response Generation:**
    *   Gemini receives the `FunctionResponse` (the web search results).
    *   It processes this new information in the context of the original query and chat history.
    *   Based on the system instruction (e.g., "Synthesize this text into an engaging, commentary-style response"), it generates the final text answer for the user. It aims to integrate the tool's findings naturally.
    *   If the tool returned an error or couldn't find the requested information, the model is instructed to inform the user gracefully.

7.  **Display Response (Streamlit UI):**
    *   The final text response generated by Gemini is received by the Streamlit application.
    *   It is displayed to the user in the chat interface (`message_placeholder.markdown(full_response_content)`).
    *   The assistant's response is added to the session message history.

## 3. The "Agent" Component

In this architecture, the **"agent" is effectively the Gemini model itself**, guided by the system instructions and equipped with tools. It's not a separate, complex orchestration layer but rather the LLM operating in tool-use mode.

*   **Perception:** The agent perceives the user's query and the ongoing chat history.
*   **Planning/Reasoning:** Guided by the system prompt, it decides whether its internal knowledge is sufficient or if external data is needed (recency, detail, commentary). If external data is required, it formulates a relevant search query.
*   **Action:**
    *   *Action 1:* Generate a direct text response.
    *   *Action 2:* Generate a `FunctionCall` to invoke the `get_search_results_with_cache` tool with specific arguments.
*   **Observation:** If a tool was called, the agent observes the `FunctionResponse` (the data retrieved from the cache or web).
*   **Final Action:** Generate the final text response based on either its internal knowledge *or* its observation of the tool results.

The sophistication lies in the LLM's ability to interpret the query, follow instructions, decide when to use tools, formulate appropriate tool inputs, and synthesize the tool's output into a coherent final answer.

## 4. Limitations

*   **Selenium Dependency & Deployment:** The most significant limitation. Requires a local browser (Chrome) and matching WebDriver (ChromeDriver). This makes deployment to standard serverless/container environments (like Streamlit Community Cloud free tier) very difficult without switching to API-based search/scraping.
*   **Web Scraping Fragility:** The CSS selectors used to extract data from Bing and target websites are prone to breaking if those sites change their layout or HTML structure. This requires ongoing maintenance.
*   **Anti-Scraping Measures:** Websites actively try to prevent automated scraping. The tool may fail due to CAPTCHAs, IP blocking, or dynamic content loading strategies that Selenium (without complex configurations) might not handle perfectly.
*   **Performance:** Selenium is resource-intensive (CPU/RAM). Live searches introduce noticeable latency compared to direct LLM responses or cache hits. FAISS search is fast, but embedding generation adds a small overhead.
*   **Accuracy & Bias:** The chatbot's responses derived from web scraping are only as accurate as the information found on the web, which can be incorrect, outdated, or biased. The LLM might also misinterpret scraped data.
*   **Cache Staleness:** The current cache implementation doesn't have an automatic invalidation mechanism. Cached results for frequently changing information (like scores from yesterday) might become stale until a similar query forces a cache miss and refresh (which might not happen if slightly different phrasings always hit the old cache entry).
*   **Cost (API Calls):** Every interaction involves at least one Gemini API call. Web searches (cache misses) involve embedding API calls. High usage could incur costs depending on Google AI pricing tiers.
*   **Context Window Limitations:** While Gemini models have large context windows, extremely long chat histories could eventually exceed the limit, impacting the quality of responses or tool use decisions.
*   **Generic Commentary:** The quality of synthesized commentary depends heavily on finding rich descriptive text online. If only factual snippets are found, the "commentary" might sound bland or repetitive.

## 5. Potential Future Improvements

This project provides a solid foundation. Here are several areas for enhancement:

*   **Core Functionality & Robustness:**
    *   **Replace Selenium with APIs:** Prioritize switching to official Search Engine APIs (Google Custom Search, Bing Web Search) or dedicated Scraping APIs (SerpApi, ScraperAPI) for reliability, reduced resource usage, and deployability.
    *   **Automated WebDriver Management:** Integrate `webdriver-manager` if sticking with Selenium locally to simplify setup.
    *   **Advanced Error Handling:** Implement more granular error handling for API calls, scraping issues, and cache operations, providing clearer feedback to the user.
    *   **Asynchronous Operations:** Explore `asyncio` and `httpx` (for API calls/requests-based scraping) or libraries like `pyppeteer` (async alternative to Selenium) to potentially improve concurrency and responsiveness, especially if multiple tools or sources are queried.

*   **Caching & State Management:**
    *   **Centralized Vector Database:** Replace the local FAISS files with a cloud-based or self-hosted vector database (e.g., Pinecone, Weaviate, Milvus, Qdrant, Supabase pgvector, Vertex AI Matching Engine). This enables:
        *   **Persistent Caching:** Cache survives application restarts and deployments.
        *   **Scalability:** Handles much larger datasets.
        *   **Shared Cache:** Potentially allows multiple instances of the app to share the cache.
    *   **Cache Invalidation Strategy:** Implement time-based expiration for cached items (e.g., scores older than 24 hours are always re-fetched) or event-driven updates.
    *   **Chat History Storage:** Store chat history persistently (e.g., in a database like Firestore, PostgreSQL, Redis) instead of relying solely on `st.session_state`. This allows conversations to resume across sessions.

*   **User Experience & Features:**
    *   **Authentication:** Add user authentication (e.g., using Streamlit Authentication components, Firebase Auth, Auth0) to personalize experiences, manage usage quotas, and secure chat history.
    *   **Voice Input/Output:** Integrate speech-to-text (e.g., browser's Web Speech API, Google Cloud Speech-to-Text) for voice queries and text-to-speech (e.g., Web Speech API, Google Cloud Text-to-Speech) for audio responses.
    *   **Live Audio Commentary Simulation:** For commentary requests, instead of just synthesizing text, generate audio using TTS with appropriate pacing and intonation based on the synthesized text. Could even mix in short generic crowd sounds for effect.
    *   **Displaying Sources:** Clearly indicate when information comes from the web search tool and provide clickable source URLs from the scraped data.
    *   **Multi-Modal Input/Output:** Explore Gemini Pro Vision capabilities to allow users to upload images (e.g., a picture of a scoreboard) for context.
    *   **User Feedback Mechanism:** Allow users to rate responses or flag inaccuracies to help improve the system.
    *   **Streaming Responses:** Utilize Gemini's streaming capabilities (`stream=True`) to display the response token-by-token for a more interactive feel, especially for longer answers.

*   **Agent & LLM Enhancements:**
    *   **More Sophisticated Agent Logic (If needed):** For more complex workflows involving multiple tools or conditional logic beyond simple tool calls, consider frameworks like LangChain or LlamaIndex to structure the agent's planning and execution phases more explicitly.
    *   **Fine-tuning (Advanced):** For highly specialized sports domains or response styles, consider fine-tuning a base Gemini model (if supported and cost-effective).
    *   **Evaluation Framework:** Implement an evaluation suite to automatically test the chatbot's performance on a set of benchmark questions (accuracy, tool use correctness, response quality).

## 6. Conclusion

The Streamlit Sports Chatbot demonstrates a practical application of combining LLMs with external tools and semantic caching. While functional, its reliance on Selenium for web scraping presents significant challenges for deployment and robustness. Addressing this limitation by transitioning to API-based data retrieval is the most critical next step for creating a more scalable and reliable application. Further enhancements in caching, state management, user experience, and agent capabilities offer exciting avenues for future development.
