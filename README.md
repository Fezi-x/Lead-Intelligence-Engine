# Kraken Lead Intelligence Engine

A stateless evaluation engine that extracts business presence from a public URL, enriches it with RAG context, and categorizes it into a specific service.

## Project Structure
- `extractor.py`: Fetches and cleans HTML to plain text.
- `rag.py`: Retrieves advisory context from the `knowledge/` directory.
- `evaluator.py`: Interacts with Groq LLM to categorize the business.
- `coda_client.py`: Saves results to a Coda table via API.
- `main.py`: Entry point orchestrating the full flow.
- `services/services.json`: Authoritative source for available services.
- `knowledge/`: Directory for RAG corpus (persona/strategy notes).
- `prompts/system_prompt.md`: Instructions for the LLM.

## Setup

1. **Create and Activate Virtual Environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install requests beautifulsoup4 python-dotenv groq
   ```

2. **Configuration**:
   - Fill in your `.env` file with `GROQ_API_KEY`, `CODA_API_TOKEN`, `CODA_DOC_ID`, and `CODA_TABLE_ID`.
   - Add your authoritative services to `services/services.json`. Format: `[{"name": "...", "description": "..."}]`.

3. **RAG Knowledge**:
   - Add markdown files (`.md`) to the `knowledge/` directory to provide additional context for the evaluation.

## Usage

Run the engine with a URL:
```bash
python main.py https://example.com
```

## Performance & Constraints
- **Total Latency Limit**: < 20s.
- **Stateless**: No caching or session storage.
- **Single Page**: Only extracts from the root URL provided.
- **RAG**: Advisory only; `services.json` is the strict authority.
