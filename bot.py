import os
import logging
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Main model first, then backups if it fails (quota, overload, etc.)
MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

user_languages = {}
user_history = {}

CONTACT_TEXT = (
    "Contact Tamim directly:\n\n"
    "WhatsApp / Phone: +8801783608061\n"
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi, I'm Tamim's AI assistant. Choose your language / ভাষা নির্বাচন করুন:",
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

    history = user_history.setdefault(uid, [])
    history.append({"role": "user", "parts": [{"text": f"(Reply in {lang}) {text}"}]})
    del history[:-10]  # keep last 10 messages

    try:
        answer = ask_gemini(history)
        history.append({"role": "model", "parts": [{"text": answer}]})
        await update.message.reply_text(answer)
    except Exception:
        log.exception("All models failed")
        history.pop()
        await update.message.reply_text(
            "Sorry, I couldn't answer that right now.\n\n" + CONTACT_TEXT,
            disable_web_page_preview=True,
        )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Tamim's AI Assistant is running...")
    app.run_polling()