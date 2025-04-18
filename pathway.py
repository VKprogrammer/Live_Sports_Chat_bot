import pathway as pw
import http.client
import json
import time
from datetime import datetime
from pathway.io.python import ConnectorSubject
import google.generativeai as genai
from dotenv import load_dotenv
import os
from pathway.xpacks.llm import embedders, parsers, splitters
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm.servers import DocumentStoreServer
from pathway.stdlib.indexing import BruteForceKnnFactory
import logging
import glob

# Set up file logging for main pipeline
logging.basicConfig(
    filename="groq_pipeline.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    force=True
)

# Custom print function to log to both file and console
def custom_print(*args, **kwargs):
    message = " ".join(map(str, args))
    logging.info(message)
    print(*args, **kwargs)

# === Configuration ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key")
CRICBUZZ_API_KEY = os.getenv("CRICBUZZ_API_KEY", "your_cricbuzz_api_key")
if not GEMINI_API_KEY or not CRICBUZZ_API_KEY:
    raise ValueError("API keys not found in .env file")

genai.configure(api_key=GEMINI_API_KEY)

# Set Pathway license key
pw.set_license_key("demo-license-key-with-telemetry")

# === Data Ingestion Pipeline ===
class LiveMatchSchema(pw.Schema):
    match_id: str
    match_data: str
    team1: str
    team2: str
    time: str

class ScorecardSchema(pw.Schema):
    match_id: str
    scorecard_data: str
    time: str

def fetch_live_matches():
    try:
        conn = http.client.HTTPSConnection("free-cricbuzz-cricket-api.p.rapidapi.com")
        headers = {
            'x-rapidapi-key': CRICBUZZ_API_KEY,
            'x-rapidapi-host': "free-cricbuzz-cricket-api.p.rapidapi.com"
        }
        conn.request("GET", "/cricket-matches-live", headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()
        custom_print(f"Live matches response: {data}")
        return json.loads(data)
    except Exception as e:
        custom_print(f"Error in fetch_live_matches: {e}")
        return {"response": []}

class LiveMatchesSubject(ConnectorSubject):
    def run(self):
        custom_print("LiveMatchesSubject started")
        while True:
            try:
                live_data = fetch_live_matches()
                custom_print(f"Live data: {json.dumps(live_data, indent=2)}")
                matches_found = False
                for series in live_data.get("response", []):
                    for match in series.get("matchList", []):
                        match_id = str(match.get("matchId"))
                        if match_id:
                            match_title = match.get("matchTitle", "Unknown vs Unknown")
                            team1, team2 = match_title.split(" vs ") if " vs " in match_title else ("Unknown", "Unknown")
                            custom_print(f"Processing match {match_id}: {team1} vs {team2}")
                            self.next(
                                match_id=match_id,
                                match_data=json.dumps(match),
                                team1=team1,
                                team2=team2,
                                time=datetime.now().isoformat()
                            )
                            matches_found = True
                if not matches_found:
                    custom_print("No live matches found, using hardcoded match for testing")
                    match_id = "104906"
                    team1, team2 = "Lions", "Titans"
                    self.next(
                        match_id=match_id,
                        match_data="{}",
                        team1=team1,
                        team2=team2,
                        time=datetime.now().isoformat()
                    )
            except Exception as e:
                custom_print(f"Error in LiveMatchesSubject: {e}")
                custom_print("Exception occurred, using hardcoded match for testing")
                match_id = "104906"
                team1, team2 = "Lions", "Titans"
                self.next(
                    match_id=match_id,
                    match_data="{}",
                    team1=team1,
                    team2=team2,
                    time=datetime.now().isoformat()
                )
            time.sleep(10)  # Reduced for faster testing

live_matches = pw.io.python.read(
    LiveMatchesSubject(),
    schema=LiveMatchSchema,
    autocommit_duration_ms=1000  # Reduced to trigger faster
)

# Debug live matches
@pw.udf
def log_match(match_id: str, team1: str, team2: str) -> bool:
    custom_print(f"Live match logged - Match ID: {match_id}, Teams: {team1} vs {team2}")
    return True

live_matches.select(logged=log_match(pw.this.match_id, pw.this.team1, pw.this.team2))

def fetch_scorecard(match_id):
    try:
        conn = http.client.HTTPSConnection("free-cricbuzz-cricket-api.p.rapidapi.com")
        headers = {
            'x-rapidapi-key': CRICBUZZ_API_KEY,
            'x-rapidapi-host': "free-cricbuzz-cricket-api.p.rapidapi.com"
        }
        conn.request("GET", f"/cricket-match-scoreboard?matchid={match_id}", headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()
        custom_print(f"Scorecard response for {match_id}: {data}")
        parsed_data = json.loads(data)
        if "response" not in parsed_data:
            custom_print(f"No scorecard data available for match {match_id}")
            return {}
        return parsed_data
    except Exception as e:
        custom_print(f"Error in fetch_scorecard for match {match_id}: {e}")
        return {}

class ScorecardSubject(ConnectorSubject):
    def __init__(self, matches_table):
        super().__init__()
        self.matches_table = matches_table

    def run(self):
        custom_print("ScorecardSubject started")
        def on_row(row):
            try:
                match_id = row["match_id"]
                custom_print(f"ScorecardSubject received row: {row}")
                if match_id == "104906":
                    scorecard_data = {
                        "response": {
                            "firstInnings": {
                                "total": {
                                    "runs": 413,
                                    "details": "7 wkts, 109.5 overs"
                                },
                                "batters": [
                                    {"name": "Player1", "runs": 150, "balls": 200},
                                    {"name": "Player2", "runs": 75, "balls": 120}
                                ]
                            },
                            "secondInnings": {
                                "total": {
                                    "runs": 17,
                                    "details": "3 wkts, 7.4 overs"
                                }
                            }
                        }
                    }
                    custom_print(f"Using hardcoded scorecard for match {match_id}")
                else:
                    scorecard_data = fetch_scorecard(match_id)
                custom_print(f"Fetched scorecard for match {match_id}: {json.dumps(scorecard_data, indent=2)}")
                self.next(
                    match_id=match_id,
                    scorecard_data=json.dumps(scorecard_data),
                    time=datetime.now().isoformat()
                )
            except Exception as e:
                custom_print(f"Error in ScorecardSubject for match {match_id}: {e}")

        pw.io.subscribe(
            self.matches_table.select(match_id=pw.this.match_id),
            on_row
        )
        while True:
            time.sleep(1)

scorecards = pw.io.python.read(
    ScorecardSubject(live_matches),
    schema=ScorecardSchema,
    autocommit_duration_ms=1000  # Reduced to trigger faster
)

# Debug scorecards
@pw.udf
def log_scorecard(match_id: str, scorecard_data: str) -> bool:
    custom_print(f"Scorecard logged - Match ID: {match_id}, Data: {scorecard_data}")
    return True

scorecards.select(logged=log_scorecard(pw.this.match_id, pw.this.scorecard_data))

# === Scorecard Formatting ===
@pw.udf
def format_scorecard(scorecard_data: str, team1: str, team2: str) -> str:
    try:
        data = json.loads(scorecard_data)
        response = data.get("response", {})
        if not response:
            return f"Match: {team1} vs {team2}\nScorecard data not available\nStatus: Ongoing"

        first_innings = response.get("firstInnings", {})
        second_innings = response.get("secondInnings", {})
        
        fi_total = first_innings.get("total", {})
        fi_runs = fi_total.get("runs", "N/A")
        fi_details = fi_total.get("details", "")
        fi_wickets = fi_details.split(" ")[1].strip("wkts,") if fi_details and "wkts" in fi_details else "N/A"
        fi_overs = fi_details.split(" ")[3].strip("overs)") if fi_details and "overs" in fi_details else "N/A"
        
        si_total = second_innings.get("total", {})
        si_runs = si_total.get("runs", "N/A")
        si_details = si_total.get("details", "")
        si_wickets = si_details.split(" ")[1].strip("wkts,") if si_details and "wkts" in si_details else "N/A"
        si_overs = si_details.split(" ")[3].strip("overs)") if si_details and "overs" in fi_details else "N/A"
        
        fi_batters = first_innings.get("batters", [])[:2]
        batting_info = ""
        if fi_batters:
            batting_info = f"\nBatting ({team1}):\n" + "\n".join(
                f"{b.get('name', 'Unknown')}: {b.get('runs', '0')} runs, {b.get('balls', '0')} balls"
                for b in fi_batters
            )
        
        formatted = (f"Match: {team1} vs {team2}\n"
                     f"{team1} Score: {fi_runs}/{fi_wickets} in {fi_overs} overs\n"
                     f"{team2} Score: {si_runs}/{si_wickets} in {si_overs} overs\n"
                     f"Status: Ongoing{batting_info}")
        custom_print(f"Formatted scorecard: {formatted}")
        return formatted
    except Exception as e:
        custom_print(f"Error formatting scorecard: {e}")
        return f"Match: {team1} vs {team2}\nScorecard data not available\nStatus: Ongoing"

scorecards_formatted = scorecards.join(
    live_matches,
    pw.left.match_id == pw.right.match_id
).select(
    match_id=pw.left.match_id,
    data=format_scorecard(pw.left.scorecard_data, pw.right.team1, pw.right.team2),
    _metadata=pw.apply(lambda: {}, pw.this.match_id)
)

# Persist scorecards manually
@pw.udf
def save_scorecard(match_id: str, data: str) -> bool:
    try:
        os.makedirs("scorecards_data", exist_ok=True)
        with open(f"scorecards_data/{match_id}.json", "w") as f:
            json.dump({
                "match_id": match_id,
                "text": data,
                "_metadata": {}
            }, f)
        custom_print(f"Saved scorecard to scorecards_data/{match_id}.json")
    except Exception as e:
        custom_print(f"Manual save failed for {match_id}: {e}")
    return True

scorecards_formatted.select(saved=save_scorecard(pw.this.match_id, pw.this.data))

# Debug formatted scorecards
@pw.udf
def log_formatted_scorecard(match_id: str, data: str) -> bool:
    custom_print(f"Formatted scorecard logged - Match ID: {match_id}, Data: {data}")
    return True

scorecards_formatted.select(logged=log_formatted_scorecard(pw.this.match_id, pw.this.data))

# Define schema for formatted scorecards
class FormattedScorecardSchema(pw.Schema):
    match_id: str
    data: str
    _metadata: dict

# Initialize scorecards_data with hardcoded match
def initialize_scorecards_data():
    if not glob.glob("scorecards_data/*.json"):
        custom_print("No scorecards found, initializing with hardcoded match")
        os.makedirs("scorecards_data", exist_ok=True)
        hardcoded_scorecard = {
            "match_id": "104906",
            "text": (
                "Match: Lions vs Titans\n"
                "Lions Score: 413/7 in 109.5 overs\n"
                "Titans Score: 17/3 in 7.4 overs\n"
                "Status: Ongoing\n"
                "Batting (Lions):\n"
                "Player1: 150 runs, 200 balls\n"
                "Player2: 75 runs, 120 balls"
            ),
            "_metadata": {}
        }
        with open("scorecards_data/104906.json", "w") as f:
            json.dump(hardcoded_scorecard, f)
        custom_print("Saved hardcoded scorecard to scorecards_data/104906.json")

# Call initialization before pipeline setup
initialize_scorecards_data()

# === Document Store Setup ===
@pw.udf
def mock_parser(data: str) -> str:
    return data

text_splitter = splitters.TokenCountSplitter(max_tokens=400)
embedding_model = "avsolatorio/GIST-small-Embedding-v0"
embedder = embedders.SentenceTransformerEmbedder(
    embedding_model,
    call_kwargs={"show_progress_bar": False}
)
index = BruteForceKnnFactory(embedder=embedder)

doc_store = DocumentStore(
    docs=scorecards_formatted,
    splitter=text_splitter,
    parser=mock_parser,
    retriever_factory=index
)

# === Debug Document Store Contents ===
debug_query_csv = "debug_queries.csv"
debug_query_content = 'query,k,metadata_filter,filepath_globpattern\n"What are the scores of the Lions vs Titans match?",3,,\n'

try:
    with open(debug_query_csv, "w") as f:
        f.write(debug_query_content)
    custom_print(f"Created debug query CSV: {debug_query_csv}")
except Exception as e:
    custom_print(f"Failed to create debug query CSV: {e}")

debug_query = pw.io.fs.read(
    debug_query_csv,
    format="csv",
    schema=DocumentStore.RetrieveQuerySchema,
    autocommit_duration_ms=1000  # Reduced to trigger faster
)

# Simplified debug query processing
class DebugQueryResultSchema(pw.Schema):
    query: str
    docs: list

debug_retrieved_docs = debug_query.select(
    query=pw.this.query,
    docs=doc_store._retriever(pw.this.query, k=pw.this.k, metadata_filter=pw.this.metadata_filter, filepath_globpattern=pw.this.filepath_globpattern)
)

@pw.udf
def log_all_docs(query: str, docs: list) -> bool:
    custom_print(f"Document store contents for query '{query}': {docs}")
    return True

debug_retrieved_docs.select(logged=log_all_docs(pw.this.query, pw.this.docs))

# === Process Queries for Answer Generation ===
class QueryResultSchema(pw.Schema):
    query: str
    docs: list

queries_formatted = debug_query.select(
    query=pw.this.query,
    k=pw.this.k,
    metadata_filter=pw.this.metadata_filter,
    filepath_globpattern=pw.this.filepath_globpattern
)

retrieved_documents = queries_formatted.select(
    query=pw.this.query,
    docs=doc_store.retrieve(pw.this.query, k=pw.this.k, metadata_filter=pw.this.metadata_filter, filepath_globpattern=pw.this.filepath_globpattern)
)

@pw.udf
def log_retrieved_docs(query: str, docs: list) -> bool:
    custom_print(f"Retrieved documents for query '{query}': {docs}")
    return True

retrieved_documents.select(logged=log_retrieved_docs(pw.this.query, pw.this.docs))

@pw.udf
def build_prompt(query: str, documents: list) -> str:
    context = []
    for doc in documents:
        if isinstance(doc, dict) and "data" in doc:
            context.append(doc["data"])
        else:
            custom_print(f"Warning: Unexpected document format: {doc}")
    context_str = "\n".join(context) if context else "No scorecard data available"
    prompt = (
        f"You are a cricket expert. Based on the following match data:\n{context_str}\n"
        f"Answer this query concisely and accurately: {query}"
    )
    custom_print(f"Prompt built for query '{query}': {prompt}")
    return prompt

prompts = retrieved_documents.select(
    query=pw.this.query,
    prompt=build_prompt(pw.this.query, pw.this.docs)
)

@pw.udf
def generate_answer(prompt: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)
        custom_print(f"Gemini response: {response.text}")
        return response.text
    except Exception as e:
        custom_print(f"LLM error: {e}")
        return "Sorry, I couldn't process your query at this time."

responses = prompts.select(
    query=pw.this.query,
    result=generate_answer(pw.this.prompt)
)

# Debug responses
@pw.udf
def log_response(query: str, result: str) -> bool:
    custom_print(f"Response generated - Query: {query}, Result: {result}")
    return True

responses.select(logged=log_response(pw.this.query, pw.this.result))

# === Run Pipeline ===
if __name__ == "__main__":
    custom_print("Starting Pathway pipeline with DocumentStoreServer...")
    server_process = None
    try:
        # Run server in a separate process
        import subprocess
        PATHWAY_PORT = 8765
        server_process = subprocess.Popen([
            "/root/gc_project/venv/bin/python", "-c",
            """
import pathway as pw
from pathway.xpacks.llm.servers import DocumentStoreServer
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm import embedders, parsers, splitters
from pathway.stdlib.indexing import BruteForceKnnFactory
import logging
import glob
import json
import time
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

def log(*args):
    message = " ".join(map(str, args))
    logger.info(message)

try:
    log("Starting server process")
    pw.set_license_key("demo-license-key-with-telemetry")
    log("License key set")
    text_splitter = splitters.TokenCountSplitter(max_tokens=400)
    log("Text splitter initialized")
    embedding_model = "avsolatorio/GIST-small-Embedding-v0"
    try:
        embedder = embedders.SentenceTransformerEmbedder(
            embedding_model,
            call_kwargs={"show_progress_bar": False}
        )
        log("Embedder initialized")
    except Exception as e:
        log("Failed to initialize embedder:", str(e))
        log("Traceback:", traceback.format_exc())
        raise
    index = BruteForceKnnFactory(embedder=embedder)
    log("Index factory created")

    json_files = []
    for _ in range(10):
        json_files = glob.glob("scorecards_data/*.json")
        if json_files:
            break
        log("No JSON files found in scorecards_data/, retrying...")
        time.sleep(1)
    if not json_files:
        log("No JSON files found after retries")
        raise ValueError("No scorecards found in scorecards_data/")

    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                log(f"File {json_file} contents: {data}")
        except Exception as e:
            log(f"Failed to read {json_file}: {e}")

    class ScorecardSchema(pw.Schema):
        match_id: str
        text: str
        _metadata: dict = pw.column_definition(dtype=dict, default_value={})

    log("Creating document input connector")
    docs = pw.io.fs.read(
        "scorecards_data/*.json",
        format="json",
        schema=ScorecardSchema,
        autocommit_duration_ms=1000
    )
    log("Document input connector created")
    log("Docs table columns:", list(docs.column_names()))

    log("Skipping table preview to avoid hang")
    log("Docs schema verified:", list(docs.column_names()))

    log("Renaming text column to data")
    try:
        renamed_docs = docs.select(
            match_id=pw.this.match_id,
            data=pw.this.text,
            _metadata=pw.this._metadata
        )
        log("Renamed table columns via select:", list(renamed_docs.column_names()))
    except Exception as e:
        log("Failed to rename with select:", str(e))
        log("Traceback:", traceback.format_exc())
        raise

    log("Initializing document store")
    try:
        doc_store = DocumentStore(
            docs=renamed_docs,
            splitter=text_splitter,
            parser=lambda x: x,
            retriever_factory=index
        )
        log("Document store initialized")
    except Exception as e:
        log("Failed to initialize document store:", str(e))
        log("Traceback:", traceback.format_exc())
        raise

    log("Creating server")
    try:
        server = DocumentStoreServer(
            host="127.0.0.1",
            port=8765,
            document_store=doc_store,
            methods=("GET", "POST")
        )
        log("Server initialized")
    except Exception as e:
        log("Failed to initialize server:", str(e))
        log("Traceback:", traceback.format_exc())
        raise

    log("Starting server")
    try:
        server.run()
        log("Server running")
    except Exception as e:
        log("Failed to run server:", str(e))
        log("Traceback:", traceback.format_exc())
        raise
except Exception as e:
    log("Server failed:", str(e))
    log("Traceback:", traceback.format_exc())
    sys.exit(1)
"""
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        custom_print(f"Started DocumentStoreServer process with PID {server_process.pid}")

        # Capture server output in real-time
        with open("server.log", "a") as log_file:
            while server_process.poll() is None:
                line = server_process.stdout.readline()
                if line:
                    log_file.write(line)
                    log_file.flush()
                    custom_print(f"Server output: {line.strip()}")
                time.sleep(0.1)

        # Run main pipeline
        pw.run()
        custom_print("Main pipeline running")
    except Exception as e:
        custom_print(f"Pipeline failed to run: {e}")
        if server_process:
            server_process.terminate()
        raise
    finally:
        if server_process:
            server_process.terminate()