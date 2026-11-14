import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from google import genai

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")  # your numeric Telegram ID (use /myid)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Main model first, then backups if it fails
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
]

user_languages = {}
user_history = {}

CONTACT_TEXT = (
    "Contact Tamim directly:\n\n"
    "WhatsApp / Phone: +8801783608061\n"
    "Telegram: https://t.me/tanvirtamim58\n"
    "Email: tanvirahmedtamim22@gmail.com\n"
    "Email (alt): tanvirtamimbsmrstu@gmail.com\n"
    "Website: https://seomedicalclinic.com/\n"
    "LinkedIn: https://www.linkedin.com/in/tanvirahmedtamim/\n"
    "Facebook: https://facebook.com/tanvirahmedtamim.4\n"
    "Instagram: https://www.instagram.com/tanvir_ahmed_tamim_/"
)

SYSTEM_PROMPT = (
    "You are the AI assistant of Md. Tanvir Ahmed Tamim (Tamim). "
    "Say you are Tamim's AI assistant if asked who you are. Never claim to be a human.\n\n"
    "Tamim's background:\n"
    "- Co-Founder and Local SEO Strategist at SEO Medical Clinic (Jan 2025 to present), Dhaka.\n"
    "- 5+ years in healthcare SEO for dental, orthodontic, dermatology practices and medical spas in the US and UK.\n"
    "- Specialties: Local SEO, Google Business Profile, Map Pack ranking, HIPAA-conscious SEO, "
    "AI Overview and LLM optimization, Ask Maps optimization, technical SEO, schema, citations, reviews, entity and brand authority.\n"
    "- Previously Local SEO and AI Search Strategist at Doctor Rank, managing 50+ healthcare practices. "
    "SEO consultant on Fiverr since 2020.\n"
    "- Education: BBA in Accounting and Information Systems, MBA in Accounting, both from GSTU.\n\n"
    "How to answer:\n"
    "1. Answer fully and practically. Accounting questions from an accounting graduate's view. "
    "SEO, local SEO and AI search questions from an agency practitioner's view.\n"
    "2. For other topics, give a short helpful answer if you can.\n"
    "3. Be direct, confident, no fluff. Never use em dashes or en dashes.\n"
    "4. Do not invent client names, results, prices or credentials not listed above.\n"
    "5. If you cannot answer well, or the user wants consulting, services or a quote, "
    "tell them to contact Tamim and say they can use /contact.\n"
    "6. Reply in the language requested."
)


# ---------- Tiny web server so Render detects an open port ----------
class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Ping).serve_forever()


# ---------- Helpers ----------
def get_lang(uid):
    return user_languages.get(uid, "English")


def lang_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("English", callback_data="lang_English"),
                InlineKeyboardButton("বাংলা", callback_data="lang_Bangla"),
            ],
            [InlineKeyboardButton("Contact Tamim", callback_data="show_contact")],
        ]
    )


async def send_owner(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send a Telegram message to the owner (you)."""
    if not OWNER_CHAT_ID:
        return
    try:
        await context.bot.send_message(OWNER_CHAT_ID, text[:4000])
    except Exception:
        log.exception("Could not send owner message")


# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi, I'm Tamim's AI assistant. Choose your language / ভাষা নির্বাচন করুন:\n\n"
        "Note: conversations with this bot may be reviewed by Tamim.",
        reply_markup=lang_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data.startswith("lang_"):
        lang = q.data.split("_", 1)[1]
        user_languages[uid] = lang
        if lang == "Bangla":
            await q.edit_message_text(
                "ভাষা বাংলা সেট হয়েছে। অ্যাকাউন্টিং, লোকাল SEO বা AI Search নিয়ে প্রশ্ন করুন। যোগাযোগ: /contact"
            )
        else:
            await q.edit_message_text(
                "Language set to English. Ask me about accounting, local SEO or AI search. Contact: /contact"
            )
    elif q.data == "show_contact":
        await q.edit_message_text(CONTACT_TEXT, disable_web_page_preview=True)


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CONTACT_TEXT, disable_web_page_preview=True)


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Select language / ভাষা নির্বাচন করুন:", reply_markup=lang_keyboard()
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your chat ID: {update.effective_user.id}")


# ---------- AI ----------
def ask_gemini(history):
    last_error = None
    for model in MODELS:
        try:
            resp = ai_client.models.generate_content(
                model=model,
                contents=history,
                config={"system_instruction": SYSTEM_PROMPT},
            )
            if resp.text:
                log.info("Answered using %s", model)
                return resp.text
            raise ValueError("Empty response")
        except Exception as e:
            log.error("Model %s failed: %s", model, e)
            last_error = e
    raise last_error


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)
    text = update.message.text
    u = update.effective_user

    # Notify owner about the new visitor message (skip if the owner is chatting)
    if str(uid) != str(OWNER_CHAT_ID):
        uname = f"@{u.username}" if u.username else "no username"
        await send_owner(
            context,
            f"New message from {u.full_name} ({uname}, id {uid}):\n\n{text[:500]}",
        )

    history = user_history.setdefault(uid, [])
    history.append({"role": "user", "parts": [{"text": f"(Reply in {lang}) {text}"}]})
    del history[:-10]

    try:
        answer = ask_gemini(history)
        history.append({"role": "model", "parts": [{"text": answer}]})
        await update.message.reply_text(answer)
    except Exception as e:
        log.exception("All models failed")
        history.pop()
        await update.message.reply_text(
            "Sorry, I couldn't answer that right now.\n\n" + CONTACT_TEXT,
            disable_web_page_preview=True,
        )
        await send_owner(context, f"Alert: all models failed.\nError: {str(e)[:500]}")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)
    await send_owner(context, f"Bot error: {str(context.error)[:500]}")


# ---------- Run ----------
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_error_handler(on_error)

    print("Tamim's AI Assistant is running...")
    app.run_polling()