# Lead Intelligence Engine

A stateless evaluation engine that extracts business presence from a public URL, enriches it with RAG context, and categorizes it into a specific service. Now featuring a Telegram Bot interface and duplicate prevention.

## Features
- **Telegram Bot Integration**: Run the engine as a bot for easy URL analysis via chat.
- **Duplicate Prevention**: Automatically checks the Coda CRM to prevent duplicate rows for the same Business URL.
- **Industry-Specific Exclusions**: Smart logic to avoid selling redundant services (e.g., no marketing packages for marketing agencies).
- **Token Usage Tracking**: Displays AI token consumption in CLI and Bot outputs.
- **Rate Limiting**: Integrated safeguard for the Telegram bot to prevent API abuse.
- **RAG Enrichment**: Uses local knowledge files to improve evaluation context.
- **Coda CRM Sync**: Auto-saves valid leads directly to your workspace.

## Project Structure
- `core.py`: **[NEW]** The central engine logic (`LeadEngine`) shared by CLI and Bot.
- `telegram_bot.py`: **[NEW]** Telegram bot interface.
- `extractor.py`: Fetches and cleans HTML to plain text.
- `rag.py`: Retrieves advisory context from the `knowledge/` directory.
- `evaluator.py`: Interacts with Groq LLM for business categorization.
- `coda_client.py`: Handles Coda API interactions (Rows, Columns, Search).
- `main.py`: CLI wrapper for the engine.
- `services/services.json`: Authoritative source for available services.
- `knowledge/`: Directory for RAG corpus and lead qualification criteria.
- `prompts/system_prompt.md`: Instructions for the LLM.

## Setup

1. **Create and Activate Virtual Environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install requests beautifulsoup4 python-dotenv groq python-telegram-bot
   ```

3. **Configuration**:
   - Create a `.env` file from the following template:
     ```env
     GROQ_API_KEY=your_groq_key
     CODA_API_TOKEN=your_coda_token
     CODA_DOC_ID=your_doc_id
     CODA_TABLE_ID=your_table_id
     TELEGRAM_BOT_TOKEN=your_telegram_token
     ```

## Usage

### 💻 Command Line (CLI)
Run a single URL analysis:
```bash
python main.py https://example.com
```

### 🤖 Telegram Bot
Start the bot for interactive usage:
```bash
python telegram_bot.py
```
**Commands:**
- `/analyze <url>`: Analyzes the provided business website.
- `/model`: Shows the current LLM model being used by the engine.
- *Alternatively, just send a URL to the bot to trigger an analysis.*

## Performance & Constraints
- **Total Latency Limit**: < 20s.
- **Duplicate Check**: Verification is based strictly on the **Business URL**.
- **Logging**: Configured to `WARNING` level to reduce terminal noise. Errors are prefixed with `CRITICAL`.
- **Stateless**: No caching; every URL is analyzed fresh.
