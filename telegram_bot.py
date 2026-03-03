import os
import time
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from core import LeadEngine

load_dotenv()

# Configure logging to be minimal as requested
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# In-memory rate limiting: {user_id: [timestamps]}
USER_REQUESTS = {}
RATE_LIMIT_MINUTES = 1
MAX_REQUESTS_PER_PERIOD = 3 

def is_rate_limited(user_id: int) -> bool:
    """Checks if a user is exceeding the rate limit."""
    now = time.time()
    if user_id not in USER_REQUESTS:
        USER_REQUESTS[user_id] = []
    
    # Clean up old timestamps
    USER_REQUESTS[user_id] = [t for t in USER_REQUESTS[user_id] if now - t < (RATE_LIMIT_MINUTES * 60)]
    
    if len(USER_REQUESTS[user_id]) >= MAX_REQUESTS_PER_PERIOD:
        return True
    
    USER_REQUESTS[user_id].append(now)
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message."""
    if not update.message:
        return
    await update.message.reply_text(
        "Welcome! I'm the Lead Intelligence Engine Bot. Generate leads for reachout purposes\n\n"
        "Commands:\n"
        "/analyze <url> - Analyze a business website\n"
        "/model - Show the current LLM model"
        "/status - Show the current status of the AI"
    )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /analyze command."""
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Please provide a URL. Usage: /analyze <url>")
        return
    
    url = context.args[0].strip()
    await process_lead_analysis(update, url)

async def handle_text_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles plain text URLs sent without a command."""
    if not update.message or not update.message.text:
        return
    url = update.message.text.strip()
    if url.startswith(("http://", "https://")):
        await process_lead_analysis(update, url)
    else:
        await update.message.reply_text("I only analyze URLs. Use /analyze <url> or just send the link.")

async def process_lead_analysis(update: Update, url: str):
    """Core logic to process and reply to lead analysis requests."""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    if is_rate_limited(user_id):
        await update.message.reply_text(f"RATE LIMIT EXCEEDED. Please wait a minute before analyzing more URLs.")
        return

    status_message = await update.message.reply_text(f"Analyzing {url}...\nThis may take up to 20 seconds.")
    
    try:
        engine = LeadEngine()
        result = engine.process_url(url)
        
        if result.get("_status") == "skipped":
            await status_message.edit_text(f"URL already exists in CRM:\n{url}\n\n{result.get('_message', 'Skipped insertion.')}")
            return

        # Success message
        response = (
            f"Analysis Complete for {result['business_name']}\n\n"
            f"Type: {result['business_type']}\n"
            f"Primary Service: {result['primary_service']}\n"
            f"Fit Score: {result['fit_score']}/100\n\n"
            f"Reasoning: {result['reasoning']}\n\n"
            f"Outreach Angle: {result['outreach_angle']}\n\n"
            f" **Latency:** {result.get('_latency', 'N/A')}\n\n"
            f"Result saved to Coda CRM."
        )
        await status_message.edit_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        error_msg = str(e)
        if "facebook.com" in url.lower():
            error_msg = "Facebook public metadata unavailable. Please provide website link if available."
        await status_message.edit_text(f"Error processing {url}:\n\n{error_msg}")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the current LLM model being used."""
    if not update.message:
        return
    try:
        engine = LeadEngine()
        model_name = engine.evaluator.model
        await update.message.reply_text(f"Current LLM Model:\n`{model_name}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Could not retrieve model info: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a beautiful status report of the AI."""
    if not update.message:
        return
    try:
        engine = LeadEngine()
        evaluator = engine.evaluator
        
        # Determine status text
        status_indicator = "[ONLINE]" if evaluator.quota_ok else "[OFFLINE/LIMITED]"
        quota_text = "WITHIN LIMITS" if evaluator.quota_ok else "RATE LIMIT REACHED / OUT OF TOKENS"
        
        u = evaluator.total_usage
        last_time = evaluator.last_run_time or "N/A"
        
        response = (
            f"SYSTEM STATUS REPORT\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"STATUS: {evaluator.status} {status_indicator}\n"
            f"LLM QUOTA: {quota_text}\n"
            f"MODEL: `{evaluator.model}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"TOKEN CONSUMPTION\n"
            f"• Total: `{u['total_tokens']:,}`\n"
            f"• Prompt: `{u['prompt_tokens']:,}`\n"
            f"• Completion: `{u['completion_tokens']:,}`\n\n"
            f"LAST ACTIVITY: `{last_time}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_Updates are tracked per session._"
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Status command error: {e}")
        await update.message.reply_text(f"ERROR: Could not retrieve AI status: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(f"INTERNAL ERROR: An error occurred while processing your request.")

if __name__ == '__main__':
    if not TOKEN or TOKEN == "your_telegram_bot_token_here":
        print("CRITICAL: TELEGRAM_BOT_TOKEN not found in .env. Please add it.")
    else:
        application = ApplicationBuilder().token(TOKEN).build()
        
        start_handler = CommandHandler('start', start)
        analyze_handler = CommandHandler('analyze', analyze_command)
        model_handler = CommandHandler('model', model_command)
        status_handler = CommandHandler('status', status_command)
        url_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_url)
        
        application.add_handler(start_handler)
        application.add_handler(analyze_handler)
        application.add_handler(model_handler)
        application.add_handler(status_handler)
        application.add_handler(url_handler)
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        print("Lead Intelligence Engine -- Application running...")
        application.run_polling()
