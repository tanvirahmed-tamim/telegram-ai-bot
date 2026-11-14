import os
import io
import re
import socket
import asyncio
import logging
import ipaddress
import threading
import urllib.error
import urllib.parse
import urllib.request
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
from google.genai import types

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")  # your numeric Telegram ID (send /myid to the bot)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ---------- Models ----------
# Fast models for simple questions, stronger models for files, math and reviews.
FAST_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]
SMART_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
TIMEOUT_FAST = 20   # seconds per model before trying the next one
TIMEOUT_SMART = 45

SMART_HINTS = re.compile(
    r"calculat|solve|journal|ledger|balance sheet|trial balance|ratio|depreciat|variance|"
    r"amortiz|equation|formula|audit|review|check|proofread|thesis|chapter|improve|feedback|"
    r"\d+\s*[\+\-\*/x×÷=]\s*\d+",
    re.I,
)

MAX_FILE_MB = 10
user_languages = {}
user_modes = {}      # "fast" (default) or "deep"
user_history = {}    # {uid: [{"role": "user"/"model", "text": "..."}]}
user_files = {}      # {uid: {"name", "mime", "data" or "text"}}

# ---------- Contact ----------
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

ABOUT_TEXT = (
    "About Tamim\n\n"
    "Md. Tanvir Ahmed Tamim is Co-Founder and Local SEO Strategist at SEO Medical Clinic, "
    "helping dental, orthodontic and dermatology practices and medical spas in the US and UK "
    "grow through local SEO, Google Business Profile optimization, AI Overview and Ask Maps "
    "optimization, and HIPAA-conscious SEO.\n\n"
    "He holds a BBA in Accounting and Information Systems and an MBA in Accounting from GSTU.\n\n"
    "Use /contact to reach him."
)

# ---------- Personality and knowledge ----------
SYSTEM_PROMPT = (
    "You are the AI assistant of Md. Tanvir Ahmed Tamim (Tamim). "
    "If asked who you are, say you are Tamim's AI assistant. Never claim to be a human.\n\n"
    "TAMIM'S BACKGROUND (use only these facts, never invent more):\n"
    "- Based in Dhaka, Bangladesh. Works with healthcare practices in the US and UK.\n"
    "- Co-Founder and Local SEO Strategist at SEO Medical Clinic (Jan 2025 to present): leads strategy, "
    "research, content planning and service innovation for dental practices, orthodontists, dermatology "
    "clinics and medical spas.\n"
    "- Local SEO and AI Search Strategist at Doctor Rank (Jun 2025 to Jun 2026), a healthcare-focused "
    "agency. Managed end-to-end local SEO campaigns for 50+ healthcare practices: audits covering GBP, "
    "on-page, citations and technical SEO; monthly reports on Map Pack rankings, GBP calls and organic "
    "traffic; GBP optimization (categories, services, attributes, photos); citation building across 50+ "
    "directories such as Healthgrades, Zocdoc, WebMD and Yelp, fixing NAP inconsistencies; content "
    "strategy for service pages, FAQs and patient education with E-E-A-T in mind; keyword research; "
    "site speed, mobile, schema (MedicalBusiness, Dentist, Physician) and crawl fixes; ethical review "
    "generation; LLM optimization so ChatGPT and Google AI can surface practices accurately.\n"
    "- SEO Consultant on Fiverr since May 2020.\n"
    "- Earlier: SEO Executive at Faisaliteb (Sep 2023 to Jul 2024); Digital Marketing Specialist at "
    "Shopno Career IT (Apr 2019 to Mar 2022).\n"
    "- 5+ years working exclusively in healthcare SEO.\n"
    "- Specializations: Local SEO and Google Business Profile, Google Maps SEO and Map Pack strategy, "
    "HIPAA-conscious SEO (forms, analytics, content), AI Overview and LLM optimization (ChatGPT, Gemini, "
    "Google AI), Ask Maps optimization, technical SEO and Core Web Vitals, topical and brand authority, "
    "online reputation management, Knowledge Graph and entity optimization, Google patents and algorithm "
    "research. Healthcare is YMYL, so accuracy matters more than in most niches.\n"
    "- Education: BBA in Accounting and Information Systems (2019 to 2024) and MBA in Accounting "
    "(2024 to 2025), both from Gopalganj Science and Technology University (GSTU).\n"
    "- Ideal clients: dental practices, orthodontic clinics, dermatology practices, medical spas.\n"
    "- Languages: English and Bangla.\n"
    "- Pricing, packages, availability, tools used, case study numbers and client names are NOT known to "
    "you. If asked, say Tamim shares those directly and point to /contact. Never guess them.\n\n"
    "YOUR JOB: help people learn, work faster, and review anything they send: SEO and websites, "
    "accounting and math, thesis and academic writing, marketing copy, spreadsheets, documents, images "
    "and general work.\n\n"
    "GENERAL RULES:\n"
    "1. Lead with the answer or verdict. No filler, no long intros.\n"
    "2. Use simple words so a learner can follow. Be practical, like an experienced practitioner.\n"
    "3. Examples must be realistic scenarios labeled 'Example:'. Never invent client names, exact results, "
    "prices, statistics or references, and never claim Tamim achieved results not listed above.\n"
    "4. Say clearly when something is uncertain, changes often (like Google updates), or depends on the situation.\n"
    "5. Formatting is plain text for Telegram. No markdown symbols (no **, no #, no backticks). "
    "Use simple CAPS headings, numbered lists and short paragraphs.\n"
    "6. Never use em dashes or en dashes.\n"
    "7. If you cannot answer well, or the user wants consulting, services or a quote, tell them to "
    "contact Tamim and mention /contact.\n"
    "8. Reply in the language requested.\n\n"
    "REVIEW RULES (for any file, text or page the user wants reviewed):\n"
    "- Give: a one-line verdict, what is strong, what is wrong or weak (most important first), and "
    "specific fixes. Quote the exact text, cell, line or page where possible.\n"
    "- SEO and websites: check title, meta description, headings, search intent match, content depth, "
    "E-E-A-T and YMYL trust signals, internal links, schema, canonical, indexability, speed, mobile, "
    "images and alt text. For local SEO also check Google Business Profile, NAP consistency, citations, "
    "reviews and map pack signals. Only judge what you can see in the data provided, and say what you "
    "could not check.\n"
    "- Accounting and math: recompute every number yourself step by step before judging. Check debits "
    "equal credits, formulas, signs, units, rounding, and the standard used (IFRS or GAAP) if relevant. "
    "State the final answer clearly and flag any assumption.\n"
    "- Thesis and academic writing: check research question, structure, argument flow, methodology, "
    "evidence, clarity, grammar and tone. Never invent references, data or quotes. Tell the user to "
    "verify every source and to write in their own words.\n"
    "- Other work (copy, emails, spreadsheets, code, images): review for the goal, clarity, errors and "
    "quick wins.\n"
    "- If a file is unreadable or incomplete, say so instead of guessing."
)

FAST_HINT = (
    "FAST MODE: be direct and tight. Answer first, then only the most useful points. "
    "Aim for under 250 words, with one short example if it helps. "
    "For reviews, list the top issues and fixes only."
)
DEEP_HINT = (
    "DEEP MODE: give a complete answer: simple explanation, how it works or step by step, "
    "a realistic example, common mistakes, and a short action checklist."
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


# ---------- Website fetch (for SEO review) ----------
def is_safe_url(url):
    """Block localhost and private network addresses."""
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        for info in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast):
                return False
        return True
    except Exception:
        return False


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_safe_url(newurl):
            raise urllib.error.URLError("Unsafe redirect blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def fetch_page_summary(url):
    if not is_safe_url(url):
        return "Page data: this URL was blocked or is not a public website."
    try:
        opener = urllib.request.build_opener(SafeRedirect)
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; TamimAssistantBot)"}
        )
        with opener.open(req, timeout=8) as r:
            status = r.status
            final_url = r.geturl()
            html = r.read(600000).decode("utf-8", errors="ignore")
    except Exception as e:
        return f"Page data: could not fetch {url} ({str(e)[:150]})."

    def first(pattern):
        m = re.search(pattern, html, re.I | re.S)
        return _clean(m.group(1)) if m else "NOT FOUND"

    title = first(r"<title[^>]*>(.*?)</title>")
    desc = first(r'<meta[^>]+name=["\']description["\'][^>]*content=["\'](.*?)["\']')
    if desc == "NOT FOUND":
        desc = first(r'<meta[^>]+content=["\'](.*?)["\'][^>]*name=["\']description["\']')
    canonical = first(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\'](.*?)["\']')
    robots = first(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'](.*?)["\']')
    lang = first(r"<html[^>]+lang=[\"'](.*?)[\"']")
    h1 = [_clean(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)][:5]
    h2 = [_clean(x) for x in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.I | re.S)][:12]
    schema = list(dict.fromkeys(re.findall(r'"@type"\s*:\s*"([^"]+)"', html)))[:10]
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    no_alt = [i for i in imgs if not re.search(r'\balt=["\'][^"\']+', i, re.I)]
    body = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    words = len(_clean(body).split())

    return (
        f"Page data fetched from {final_url} (HTTP {status}):\n"
        f"- Title ({len(title)} chars): {title}\n"
        f"- Meta description ({len(desc)} chars): {desc}\n"
        f"- Canonical: {canonical}\n"
        f"- Robots meta: {robots}\n"
        f"- HTML lang: {lang}\n"
        f"- H1 tags ({len(h1)}): {h1}\n"
        f"- H2 tags (first 12): {h2}\n"
        f"- Schema types found: {schema or 'none found'}\n"
        f"- Images: {len(imgs)} total, {len(no_alt)} without alt text\n"
        f"- Approx. visible word count: {words}\n"
        "(Only the raw HTML was checked. Speed, mobile, backlinks, rankings and JavaScript-rendered "
        "content were NOT checked.)"
    )


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
    if not OWNER_CHAT_ID:
        return
    try:
        await context.bot.send_message(OWNER_CHAT_ID, text[:4000])
    except Exception:
        log.exception("Could not send owner message")


def split_text(text, limit=3900):
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks


async def reply_long(update: Update, text: str):
    for chunk in split_text(text):
        await update.message.reply_text(chunk, disable_web_page_preview=True)


def file_to_part(f):
    if "text" in f:
        return types.Part(text=f"[Uploaded file: {f['name']}]\n{f['text']}")
    return types.Part.from_bytes(data=f["data"], mime_type=f["mime"])


def pick_models(text, has_file, mode):
    if has_file or mode == "deep" or len(text or "") > 800 or SMART_HINTS.search(text or ""):
        return SMART_MODELS, TIMEOUT_SMART
    return FAST_MODELS, TIMEOUT_FAST


# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi, I'm Tamim's AI assistant. Choose your language / ভাষা নির্বাচন করুন:\n\n"
        "I can review and explain: SEO and websites (paste a link), accounting and math, "
        "thesis writing, copy, and files (PDF, Word, text, CSV, images).\n"
        "Send a file with a caption like 'review this'.\n\n"
        "/fast = short, quick answers (default)\n"
        "/deep = full answers with examples\n"
        "/newchat = start a new topic\n"
        "/about = about Tamim\n"
        "/contact = reach Tamim\n\n"
        "Please do not upload confidential or patient data. "
        "Conversations may be reviewed by Tamim.",
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
                "ভাষা বাংলা সেট হয়েছে। প্রশ্ন করুন, লিংক দিন বা রিভিউয়ের জন্য ফাইল পাঠান।\n"
                "/fast দ্রুত উত্তর, /deep বিস্তারিত উত্তর, /newchat নতুন টপিক, /contact যোগাযোগ"
            )
        else:
            await q.edit_message_text(
                "Language set to English. Ask a question, paste a link, or send a file to review.\n"
                "/fast quick answers, /deep full answers, /newchat new topic, /contact reach Tamim"
            )
    elif q.data == "show_contact":
        await q.edit_message_text(CONTACT_TEXT, disable_web_page_preview=True)


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CONTACT_TEXT, disable_web_page_preview=True)


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ABOUT_TEXT)


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Select language / ভাষা নির্বাচন করুন:", reply_markup=lang_keyboard()
    )


async def fast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_modes[update.effective_user.id] = "fast"
    await update.message.reply_text("Fast mode on. Short, direct answers.")


async def deep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_modes[update.effective_user.id] = "deep"
    await update.message.reply_text(
        "Deep mode on. Full answers with examples (a bit slower). Use /fast to switch back."
    )


async def newchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_history.pop(uid, None)
    user_files.pop(uid, None)
    await update.message.reply_text("Done. History and uploaded file cleared. Start a new topic.")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your chat ID: {update.effective_user.id}")


# ---------- AI ----------
def build_contents(history, user_text, file_info):
    contents = [
        types.Content(role=h["role"], parts=[types.Part(text=h["text"])])
        for h in history
    ]
    parts = []
    if file_info:
        parts.append(file_to_part(file_info))
    parts.append(types.Part(text=user_text))
    contents.append(types.Content(role="user", parts=parts))
    return contents


async def ask_gemini(contents, models, timeout):
    last_error = None
    for model in models:
        try:
            resp = await asyncio.wait_for(
                ai_client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                ),
                timeout=timeout,
            )
            if resp.text:
                log.info("Answered using %s", model)
                return resp.text
            raise ValueError("Empty response")
        except Exception as e:
            log.error("Model %s failed: %s", model, repr(e)[:300])
            last_error = e
    raise last_error


async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str,
                  note: str = "", extra: str = ""):
    uid = update.effective_user.id
    lang = get_lang(uid)
    mode = user_modes.get(uid, "fast")
    history = user_history.setdefault(uid, [])
    file_info = user_files.get(uid)

    hint = DEEP_HINT if mode == "deep" else FAST_HINT
    prompt = f"(Reply in {lang}. {hint})\n\n{user_text}"
    if extra:
        prompt += f"\n\n{extra}"

    models, timeout = pick_models(user_text, bool(file_info), mode)
    contents = build_contents(history, prompt, file_info)

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    try:
        answer = await ask_gemini(contents, models, timeout)
        history.append({"role": "user", "text": f"{note}{user_text}"})
        history.append({"role": "model", "text": answer})
        del history[:-6]
        await reply_long(update, answer)
    except Exception as e:
        log.exception("All models failed")
        await update.message.reply_text(
            "Sorry, I couldn't answer that right now. Please try again in a minute.\n\n" + CONTACT_TEXT,
            disable_web_page_preview=True,
        )
        await send_owner(context, f"Alert: all models failed.\nError: {str(e)[:500]}")


# ---------- Handlers ----------
URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.I)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = update.effective_user
    text = update.message.text

    if str(uid) != str(OWNER_CHAT_ID):
        uname = f"@{u.username}" if u.username else "no username"
        await send_owner(
            context, f"New message from {u.full_name} ({uname}, id {uid}):\n\n{text[:500]}"
        )

    extra = ""
    m = URL_RE.search(text)
    if m:
        url = m.group(1).rstrip(".,);]")
        if url.lower().startswith("www."):
            url = "https://" + url
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        extra = await asyncio.to_thread(fetch_page_summary, url)

    await respond(update, context, text, extra=extra)


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = update.effective_user
    msg = update.message
    caption = (msg.caption or "").strip()

    if msg.document:
        tg_file_obj = msg.document
        name = msg.document.file_name or "document"
        mime = msg.document.mime_type or ""
        size = msg.document.file_size or 0
    elif msg.photo:
        tg_file_obj = msg.photo[-1]
        name = "photo.jpg"
        mime = "image/jpeg"
        size = tg_file_obj.file_size or 0
    else:
        return

    if size > MAX_FILE_MB * 1024 * 1024:
        await msg.reply_text(f"File is too large. Please send a file under {MAX_FILE_MB} MB.")
        return

    lower = name.lower()
    supported = (
        lower.endswith((".pdf", ".txt", ".md", ".csv", ".docx", ".png", ".jpg", ".jpeg", ".webp"))
        or mime.startswith("image/")
    )
    if not supported:
        await msg.reply_text(
            "I can review PDF, Word (.docx), text, CSV and image files. Please send one of those."
        )
        return

    if str(uid) != str(OWNER_CHAT_ID):
        uname = f"@{u.username}" if u.username else "no username"
        await send_owner(
            context,
            f"File from {u.full_name} ({uname}, id {uid}): {name}\nCaption: {caption[:300]}",
        )

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    try:
        tg_file = await context.bot.get_file(tg_file_obj.file_id)
        data = bytes(await tg_file.download_as_bytearray())

        if lower.endswith(".pdf") or mime == "application/pdf":
            info = {"name": name, "mime": "application/pdf", "data": data}
        elif lower.endswith(".docx"):
            from docx import Document

            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
            for table in doc.tables:
                for row in table.rows:
                    text += "\n" + " | ".join(c.text for c in row.cells)
            info = {"name": name, "text": text[:150000]}
        elif lower.endswith((".txt", ".md", ".csv")):
            info = {"name": name, "text": data.decode("utf-8", errors="ignore")[:150000]}
        else:
            if lower.endswith(".png"):
                mime = "image/png"
            elif lower.endswith(".webp"):
                mime = "image/webp"
            elif not mime.startswith("image/"):
                mime = "image/jpeg"
            info = {"name": name, "mime": mime, "data": data}
    except Exception:
        log.exception("File read failed")
        await msg.reply_text("Sorry, I could not read that file. Try another format, like PDF.")
        return

    user_files[uid] = info
    request = caption or (
        "Review this file. Give the verdict, what is strong, what is wrong or weak, "
        "and specific fixes."
    )
    await respond(update, context, request, note=f"[File: {name}] ")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)
    await send_owner(context, f"Bot error: {str(context.error)[:500]}")


# ---------- Run ----------
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("fast", fast_cmd))
    app.add_handler(CommandHandler("deep", deep_cmd))
    app.add_handler(CommandHandler("newchat", newchat))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_error_handler(on_error)

    print("Tamim's AI Assistant is running...")
    app.run_polling()