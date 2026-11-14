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
# Set NOTIFY_NEW_MESSAGES=off in Render to stop forwarding visitor messages to you
NOTIFY_NEW_MESSAGES = os.getenv("NOTIFY_NEW_MESSAGES", "on").strip().lower() != "off"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ---------- Models ----------
FAST_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]
SMART_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
TIMEOUT_FAST = 20
TIMEOUT_SMART = 45

SMART_HINTS = re.compile(
    r"calculat|solve|journal|ledger|balance sheet|trial balance|ratio|depreciat|variance|"
    r"amortiz|equation|formula|audit|review|check|proofread|thesis|chapter|improve|feedback|"
    r"\d+\s*[\+\-\*/x×÷=]\s*\d+",
    re.I,
)

MAX_FILE_MB = 10
user_languages = {}
user_modes = {}
user_history = {}
user_files = {}

# ---------- Contact ----------
CONTACT_TEXT = (
    "📞 CONTACT TAMIM\n\n"
    "WhatsApp / Phone: +8801783608061\n"
    "Telegram: https://t.me/tanvirtamim58\n"
    "Email: tanvirahmedtamim22@gmail.com\n"
    "Email (alt): tanvirtamimbsmrstu@gmail.com\n"
    "Website: https://seomedicalclinic.com/\n"
    "LinkedIn: https://www.linkedin.com/in/tanvirahmedtamim/\n"
    "Facebook: https://facebook.com/tanvirahmedtamim.4\n"
    "Instagram: https://www.instagram.com/tanvir_ahmed_tamim_/"
)

# ---------- Texts (English and Bangla) ----------
LINE = "━━━━━━━━━━━━━━━━━━"

TXT = {
    "English": {
        "welcome": (
            "✨ Welcome, {name}.\n\n"
            "It is a genuine pleasure to have you here. I am the AI assistant of "
            "Md. Tanvir Ahmed Tamim, Co-Founder at SEO Medical Clinic and Local AI Search Specialist.\n\n"
            "Kindly select your preferred language to begin.\n"
            "অনুগ্রহ করে আপনার পছন্দের ভাষা নির্বাচন করুন।"
        ),
        "menu": (
            LINE + "\n🚀 AT YOUR SERVICE, {name}\n" + LINE + "\n\n"
            "How may I assist you today? Please choose an option below, or simply type your question, "
            "share a website link, or send a file for review.\n\n"
            "⚡ /fast  concise answers\n"
            "🧠 /deep  detailed answers with examples\n"
            "🔄 /newchat  begin a fresh topic\n"
            "🧭 /menu  return to this menu\n\n"
            "For your privacy and safety, please avoid sharing confidential or patient data."
        ),
        "help": (
            "💡 HOW I CAN HELP\n\n"
            "1. Search and AI visibility\n"
            "Strategy and guidance on SEO, local SEO, Google Business Profile, AI Overviews, "
            "LLM optimization, semantic search and entity optimization.\n\n"
            "2. Website and content review\n"
            "Share a link or upload a file (PDF, Word, text, CSV, image) and receive a clear verdict, "
            "key strengths, weaknesses and specific fixes.\n\n"
            "3. Accounting, math and research\n"
            "Explanations, step by step calculations, financial statement checks, thesis structure, "
            "methodology and academic writing feedback.\n\n"
            "4. Everyday productivity\n"
            "Professional emails, marketing copy, documents, spreadsheets and image review.\n\n"
            "5. Automation and growth ideas\n"
            "Guidance on bot development, programmatic SEO and workflow improvement.\n\n"
            "To learn more about Tamim, tap About Tamim."
        ),
        "about": (
            "👤 ABOUT TAMIM\n\n"
            "Md. Tanvir Ahmed Tamim\n"
            "Co-Founder at SEO Medical Clinic | Local AI Search Specialist\n"
            "Dhaka, Bangladesh\n\n"
            "Tamim has spent more than five years working exclusively in healthcare SEO, helping dental, "
            "orthodontic and dermatology practices and medical spas in the United States and the United Kingdom "
            "build stronger local visibility and lasting online trust. He also researches Google patents and "
            "search algorithms closely.\n\n"
            "EXPERIENCE\n"
            "• Co-Founder and Local SEO Strategist, SEO Medical Clinic (2025 to present)\n"
            "• Local SEO and AI Search Strategist, Doctor Rank (2025 to 2026), managing 50+ healthcare practices\n"
            "• SEO Consultant, Fiverr (2020 to present)\n"
            "• SEO Executive, Faisaliteb (2023 to 2024)\n"
            "• Digital Marketing Specialist, Shopno Career IT (2019 to 2022)\n\n"
            "EDUCATION\n"
            "• MBA in Accounting and Information Systems, GSTU (Session 2022-23)\n"
            "• BBA in Accounting and Information Systems, GSTU (Session 2018-19)\n\n"
            "Languages: English and Bangla\n\n"
            "To see his full range of skills, tap Search Expertise. To connect with him directly, tap Contact."
        ),
        "expertise": (
            "🔎 TAMIM'S EXPERTISE\n\n"
            "LOCAL AND AI SEARCH\n"
            "• Local SEO and Google Business Profile optimization\n"
            "• Google Maps SEO and Map Pack strategy\n"
            "• Ask Maps optimization\n"
            "• AI Overview optimization\n"
            "• LLM optimization (ChatGPT, Gemini, Google AI)\n\n"
            "SEARCH FOUNDATIONS\n"
            "• Semantic search optimization\n"
            "• Entity and Knowledge Graph optimization\n"
            "• Topical and brand authority\n"
            "• Technical SEO and Core Web Vitals\n"
            "• Schema and structured data\n\n"
            "BRAND AND COMMUNITY\n"
            "• Reddit and community brand mention strategy\n"
            "• Online reputation management\n"
            "• HIPAA-conscious SEO\n\n"
            "RESEARCH AND AUTOMATION\n"
            "• Google patents and search algorithm research\n"
            "• Bot development (AI and Telegram assistants)\n"
            "• Programmatic SEO (intermediate level)"
        ),
        "lang_set": "✅ Language set to English.",
        "fast_on": "⚡ Fast mode is on. You will receive concise, direct answers.",
        "deep_on": "🧠 Deep mode is on. You will receive complete answers with examples. Use /fast to switch back.",
        "cleared": "✅ Done. Your history and uploaded file have been cleared. Please begin a new topic whenever you are ready.",
        "sorry": "I sincerely apologize, I was unable to answer that just now. Kindly try again in a minute.\n\n",
        "too_large": "Thank you for your file. It is too large for me to process. Please send a file under {mb} MB.",
        "unsupported": "I can review PDF, Word (.docx), text, CSV and image files. Kindly send one of those formats.",
        "unreadable": "I apologize, I could not read that file. Please try another format, such as PDF.",
        "review_default": "Review this file. Give the verdict, what is strong, what is weak or wrong, and specific fixes.",
        "btn_help": "💡 How I Can Help",
        "btn_about": "👤 About Tamim",
        "btn_expertise": "🔎 Search Expertise",
        "btn_contact": "📞 Contact Tamim",
        "btn_lang": "🌐 Language",
        "btn_back": "⬅️ Back to Menu",
        "guest": "Guest",
    },
    "Bangla": {
        "welcome": (
            "✨ স্বাগতম, {name}।\n\n"
            "আপনাকে এখানে স্বাগত জানাতে পেরে আমি সত্যিই আনন্দিত। আমি মো. তানভীর আহমেদ তামিমের এআই অ্যাসিস্ট্যান্ট। "
            "তিনি SEO Medical Clinic-এর কো-ফাউন্ডার এবং Local AI Search Specialist।\n\n"
            "অনুগ্রহ করে শুরু করতে আপনার পছন্দের ভাষা নির্বাচন করুন।\n"
            "Kindly select your preferred language."
        ),
        "menu": (
            LINE + "\n🚀 আপনার সেবায় প্রস্তুত, {name}\n" + LINE + "\n\n"
            "আজ আমি আপনাকে কীভাবে সহায়তা করতে পারি? অনুগ্রহ করে নিচের অপশন থেকে বেছে নিন, "
            "অথবা সরাসরি আপনার প্রশ্ন লিখুন, ওয়েবসাইটের লিংক দিন, কিংবা রিভিউয়ের জন্য ফাইল পাঠান।\n\n"
            "⚡ /fast  সংক্ষিপ্ত উত্তর\n"
            "🧠 /deep  উদাহরণসহ বিস্তারিত উত্তর\n"
            "🔄 /newchat  নতুন বিষয় শুরু করতে\n"
            "🧭 /menu  এই মেনুতে ফিরে আসতে\n\n"
            "আপনার নিরাপত্তার স্বার্থে অনুগ্রহ করে গোপনীয় বা রোগীর তথ্য শেয়ার করা থেকে বিরত থাকুন।"
        ),
        "help": (
            "💡 আমি যেভাবে সহায়তা করতে পারি\n\n"
            "১. সার্চ ও AI ভিজিবিলিটি\n"
            "SEO, লোকাল SEO, Google Business Profile, AI Overviews, LLM optimization, "
            "semantic search ও entity optimization বিষয়ে কৌশল ও দিকনির্দেশনা।\n\n"
            "২. ওয়েবসাইট ও কনটেন্ট রিভিউ\n"
            "লিংক দিন বা ফাইল (PDF, Word, টেক্সট, CSV, ছবি) পাঠান। আপনি পাবেন স্পষ্ট মূল্যায়ন, "
            "শক্তিশালী দিক, দুর্বলতা এবং নির্দিষ্ট সমাধান।\n\n"
            "৩. অ্যাকাউন্টিং, গণিত ও গবেষণা\n"
            "ব্যাখ্যা, ধাপে ধাপে হিসাব, আর্থিক বিবরণীর যাচাই, থিসিসের কাঠামো, "
            "মেথডোলজি এবং একাডেমিক লেখার মতামত।\n\n"
            "৪. দৈনন্দিন কাজে সহায়তা\n"
            "পেশাদার ইমেইল, মার্কেটিং কপি, ডকুমেন্ট, স্প্রেডশিট ও ছবির রিভিউ।\n\n"
            "৫. অটোমেশন ও গ্রোথ আইডিয়া\n"
            "বট ডেভেলপমেন্ট, programmatic SEO এবং ওয়ার্কফ্লো উন্নয়নে দিকনির্দেশনা।\n\n"
            "তামিম সম্পর্কে আরও জানতে About Tamim বাটনে চাপ দিন।"
        ),
        "about": (
            "👤 তামিম সম্পর্কে\n\n"
            "মো. তানভীর আহমেদ তামিম\n"
            "Co-Founder at SEO Medical Clinic | Local AI Search Specialist\n"
            "ঢাকা, বাংলাদেশ\n\n"
            "তামিম পাঁচ বছরেরও বেশি সময় ধরে একচেটিয়াভাবে হেলথকেয়ার SEO নিয়ে কাজ করছেন। "
            "তিনি যুক্তরাষ্ট্র ও যুক্তরাজ্যের ডেন্টাল, অর্থোডন্টিক ও ডার্মাটোলজি প্র্যাকটিস এবং মেডিকেল স্পা-কে "
            "শক্তিশালী লোকাল ভিজিবিলিটি ও দীর্ঘস্থায়ী অনলাইন আস্থা গড়তে সহায়তা করেন। "
            "পাশাপাশি তিনি Google patents ও সার্চ অ্যালগরিদম নিয়ে গভীর গবেষণা করেন।\n\n"
            "অভিজ্ঞতা\n"
            "• Co-Founder ও Local SEO Strategist, SEO Medical Clinic (২০২৫ থেকে বর্তমান)\n"
            "• Local SEO ও AI Search Strategist, Doctor Rank (২০২৫ থেকে ২০২৬), ৫০+ হেলথকেয়ার প্র্যাকটিস পরিচালনা\n"
            "• SEO Consultant, Fiverr (২০২০ থেকে বর্তমান)\n"
            "• SEO Executive, Faisaliteb (২০২৩ থেকে ২০২৪)\n"
            "• Digital Marketing Specialist, Shopno Career IT (২০১৯ থেকে ২০২২)\n\n"
            "শিক্ষা\n"
            "• MBA in Accounting and Information Systems, GSTU (সেশন ২০২২-২৩)\n"
            "• BBA in Accounting and Information Systems, GSTU (সেশন ২০১৮-১৯)\n\n"
            "ভাষা: ইংরেজি ও বাংলা\n\n"
            "তাঁর দক্ষতার পূর্ণ তালিকা দেখতে Search Expertise বাটনে চাপ দিন। সরাসরি যোগাযোগ করতে Contact বাটনে চাপ দিন।"
        ),
        "expertise": (
            "🔎 তামিমের দক্ষতা\n\n"
            "লোকাল ও AI সার্চ\n"
            "• Local SEO ও Google Business Profile optimization\n"
            "• Google Maps SEO ও Map Pack কৌশল\n"
            "• Ask Maps optimization\n"
            "• AI Overview optimization\n"
            "• LLM optimization (ChatGPT, Gemini, Google AI)\n\n"
            "সার্চ ফাউন্ডেশন\n"
            "• Semantic search optimization\n"
            "• Entity ও Knowledge Graph optimization\n"
            "• Topical ও brand authority\n"
            "• Technical SEO ও Core Web Vitals\n"
            "• Schema ও structured data\n\n"
            "ব্র্যান্ড ও কমিউনিটি\n"
            "• Reddit ও কমিউনিটি ব্র্যান্ড মেনশন কৌশল\n"
            "• Online reputation management\n"
            "• HIPAA-conscious SEO\n\n"
            "গবেষণা ও অটোমেশন\n"
            "• Google patents ও সার্চ অ্যালগরিদম গবেষণা\n"
            "• বট ডেভেলপমেন্ট (AI ও Telegram অ্যাসিস্ট্যান্ট)\n"
            "• Programmatic SEO (ইন্টারমিডিয়েট লেভেল)"
        ),
        "lang_set": "✅ ভাষা বাংলা সেট করা হয়েছে।",
        "fast_on": "⚡ ফাস্ট মোড চালু হয়েছে। আপনি সংক্ষিপ্ত ও সরাসরি উত্তর পাবেন।",
        "deep_on": "🧠 ডিপ মোড চালু হয়েছে। আপনি উদাহরণসহ পূর্ণাঙ্গ উত্তর পাবেন। ফিরে যেতে /fast লিখুন।",
        "cleared": "✅ সম্পন্ন হয়েছে। আপনার হিস্টোরি ও আপলোড করা ফাইল মুছে ফেলা হয়েছে। প্রস্তুত হলে নতুন বিষয় শুরু করুন।",
        "sorry": "আন্তরিকভাবে দুঃখিত, এই মুহূর্তে উত্তর দিতে পারিনি। অনুগ্রহ করে এক মিনিট পর আবার চেষ্টা করুন।\n\n",
        "too_large": "আপনার ফাইলের জন্য ধন্যবাদ। ফাইলটি প্রসেস করার জন্য অনেক বড়। অনুগ্রহ করে {mb} MB এর কম আকারের ফাইল পাঠান।",
        "unsupported": "আমি PDF, Word (.docx), টেক্সট, CSV এবং ছবি রিভিউ করতে পারি। অনুগ্রহ করে এগুলোর কোনো একটি ফরম্যাটে পাঠান।",
        "unreadable": "দুঃখিত, ফাইলটি পড়তে পারিনি। অনুগ্রহ করে অন্য ফরম্যাটে, যেমন PDF, পাঠান।",
        "review_default": "এই ফাইলটি রিভিউ করুন। মূল্যায়ন, শক্তিশালী দিক, দুর্বল বা ভুল অংশ এবং নির্দিষ্ট সমাধান জানান।",
        "btn_help": "💡 কীভাবে সহায়তা করি",
        "btn_about": "👤 তামিম সম্পর্কে",
        "btn_expertise": "🔎 দক্ষতা",
        "btn_contact": "📞 যোগাযোগ",
        "btn_lang": "🌐 ভাষা",
        "btn_back": "⬅️ মেনুতে ফিরুন",
        "guest": "অতিথি",
    },
}


def tx(lang, key, **kw):
    s = TXT.get(lang, TXT["English"])[key]
    return s.format(**kw) if kw else s


# ---------- Personality and knowledge ----------
SYSTEM_PROMPT = (
    "You are the AI assistant of Md. Tanvir Ahmed Tamim (Tamim), Co-Founder at SEO Medical Clinic and "
    "Local AI Search Specialist. If asked who you are, say you are Tamim's AI assistant. "
    "Never claim to be a human.\n\n"
    "TONE: Speak with exceptional professionalism and warm respect. Be courteous, polished, composed and "
    "confident, never arrogant or condescending. Address the user by name occasionally (not in every message). "
    "Use gracious phrasing such as 'Certainly', 'With pleasure', 'Kindly', 'I would recommend'. "
    "No slang, no casual filler. In Bangla, use the respectful 'আপনি' form with formal, polite Bangla, "
    "and keep technical terms in English.\n\n"
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
    "- 5+ years working exclusively in healthcare SEO. Healthcare is YMYL, so accuracy matters more than "
    "in most niches.\n"
    "- EXPERTISE, organized:\n"
    "  Local and AI Search: Local SEO and Google Business Profile optimization; Google Maps SEO and Map "
    "Pack strategy; Ask Maps optimization; AI Overview optimization; LLM optimization (ChatGPT, Gemini, "
    "Google AI).\n"
    "  Search Foundations: semantic search optimization; entity and Knowledge Graph optimization; topical "
    "and brand authority; technical SEO and Core Web Vitals; schema and structured data.\n"
    "  Brand and Community: Reddit and community brand mention strategy; online reputation management; "
    "HIPAA-conscious SEO (forms, analytics, content).\n"
    "  Research and Automation: Google patents and search algorithm research; bot development (AI and "
    "Telegram assistants); programmatic SEO at an intermediate level (do not overstate it).\n"
    "- Education: MBA in Accounting and Information Systems (Session 2022-23) and BBA in Accounting and "
    "Information Systems (Session 2018-19), both from Gopalganj Science and Technology University (GSTU).\n"
    "- Ideal clients: dental practices, orthodontic clinics, dermatology practices, medical spas.\n"
    "- Languages: English and Bangla.\n"
    "- Pricing, packages, availability, tools used, case study numbers and client names are NOT known to "
    "you. If asked, say Tamim shares those directly and point to /contact. Never guess them.\n"
    "- If someone wants to know about Tamim, give a complete, well organized picture from the facts above.\n\n"
    "YOUR JOB: help people learn, work faster, and review anything they send: SEO and websites, "
    "accounting and math, thesis and academic writing, marketing copy, spreadsheets, documents, images "
    "and general work.\n\n"
    "GENERAL RULES:\n"
    "1. Lead with the answer or verdict. No filler, no long intros.\n"
    "2. Use clear, simple words so a learner can follow. Be practical, like an experienced practitioner.\n"
    "3. Examples must be realistic scenarios labeled 'Example:'. Never invent client names, exact results, "
    "prices, statistics or references, and never claim Tamim achieved results not listed above.\n"
    "4. Say clearly when something is uncertain, changes often (like Google updates), or depends on the situation.\n"
    "5. Formatting is plain text for Telegram. No markdown symbols (no **, no #, no backticks). "
    "Use simple CAPS headings, numbered lists and short paragraphs.\n"
    "6. Never use em dashes or en dashes.\n"
    "7. If you cannot answer well, or the user wants consulting, services or a quote, kindly invite them to "
    "contact Tamim and mention /contact.\n"
    "8. Reply in the language requested.\n\n"
    "REVIEW RULES (for any file, text or page the user wants reviewed):\n"
    "- Give: a one-line verdict, what is strong, what is wrong or weak (most important first), and "
    "specific fixes. Quote the exact text, cell, line or page where possible.\n"
    "- SEO and websites: check title, meta description, headings, search intent match, content depth, "
    "semantic coverage and entities, E-E-A-T and YMYL trust signals, internal links, schema, canonical, "
    "indexability, speed, mobile, images and alt text. For local SEO also check Google Business Profile, "
    "NAP consistency, citations, reviews and map pack signals. Only judge what you can see in the data "
    "provided, and say what you could not check.\n"
    "- Accounting and math: recompute every number yourself step by step before judging. Check debits "
    "equal credits, formulas, signs, units, rounding, and the standard used (IFRS or GAAP) if relevant. "
    "State the final answer clearly and flag any assumption.\n"
    "- Thesis and academic writing: check research question, structure, argument flow, methodology, "
    "evidence, clarity, grammar and tone. Never invent references, data or quotes. Advise the user to "
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


def display_name(user, lang):
    return (user.first_name or "").strip() or tx(lang, "guest")


def lang_keyboard():
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"),
            InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_Bangla"),
        ]]
    )


def menu_keyboard(lang):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tx(lang, "btn_help"), callback_data="menu_help"),
                InlineKeyboardButton(tx(lang, "btn_about"), callback_data="menu_about"),
            ],
            [
                InlineKeyboardButton(tx(lang, "btn_expertise"), callback_data="menu_expertise"),
                InlineKeyboardButton(tx(lang, "btn_contact"), callback_data="show_contact"),
            ],
            [InlineKeyboardButton(tx(lang, "btn_lang"), callback_data="open_lang")],
        ]
    )


def back_keyboard(lang):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(tx(lang, "btn_back"), callback_data="menu_main")]]
    )


async def send_owner(context: ContextTypes.DEFAULT_TYPE, text: str):
    if not OWNER_CHAT_ID:
        return
    try:
        await context.bot.send_message(OWNER_CHAT_ID, text[:4000])
    except Exception:
        log.exception("Could not send owner message")


async def notify_visitor(context, user, text):
    """Forward visitor activity to the owner (can be switched off with NOTIFY_NEW_MESSAGES=off)."""
    if not NOTIFY_NEW_MESSAGES:
        return
    if str(user.id) == str(OWNER_CHAT_ID):
        return
    uname = f"@{user.username}" if user.username else "no username"
    await send_owner(context, f"New activity from {user.full_name} ({uname}, id {user.id}):\n\n{text[:500]}")


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
    user = update.effective_user
    lang = get_lang(user.id)
    await update.message.reply_text(
        tx("English", "welcome", name=display_name(user, "English")),
        reply_markup=lang_keyboard(),
    )


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(user.id)
    await update.message.reply_text(
        tx(lang, "menu", name=display_name(user, lang)), reply_markup=menu_keyboard(lang)
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(tx(lang, "help"), reply_markup=back_keyboard(lang))


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(tx(lang, "about"), reply_markup=back_keyboard(lang))


async def expertise_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(tx(lang, "expertise"), reply_markup=back_keyboard(lang))


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(
        CONTACT_TEXT, disable_web_page_preview=True, reply_markup=back_keyboard(lang)
    )


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Select language / ভাষা নির্বাচন করুন:", reply_markup=lang_keyboard()
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    uid = user.id
    data = q.data
    lang = get_lang(uid)

    if data.startswith("lang_"):
        lang = data.split("_", 1)[1]
        user_languages[uid] = lang
        await q.edit_message_text(
            tx(lang, "menu", name=display_name(user, lang)), reply_markup=menu_keyboard(lang)
        )
    elif data == "open_lang":
        await q.edit_message_text(
            "Select language / ভাষা নির্বাচন করুন:", reply_markup=lang_keyboard()
        )
    elif data == "menu_main":
        await q.edit_message_text(
            tx(lang, "menu", name=display_name(user, lang)), reply_markup=menu_keyboard(lang)
        )
    elif data == "menu_help":
        await q.edit_message_text(tx(lang, "help"), reply_markup=back_keyboard(lang))
    elif data == "menu_about":
        await q.edit_message_text(tx(lang, "about"), reply_markup=back_keyboard(lang))
    elif data == "menu_expertise":
        await q.edit_message_text(tx(lang, "expertise"), reply_markup=back_keyboard(lang))
    elif data == "show_contact":
        await q.edit_message_text(
            CONTACT_TEXT, disable_web_page_preview=True, reply_markup=back_keyboard(lang)
        )


async def fast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_modes[uid] = "fast"
    await update.message.reply_text(tx(get_lang(uid), "fast_on"))


async def deep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_modes[uid] = "deep"
    await update.message.reply_text(tx(get_lang(uid), "deep_on"))


async def newchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_history.pop(uid, None)
    user_files.pop(uid, None)
    await update.message.reply_text(tx(get_lang(uid), "cleared"))


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
    user = update.effective_user
    uid = user.id
    lang = get_lang(uid)
    mode = user_modes.get(uid, "fast")
    history = user_history.setdefault(uid, [])
    file_info = user_files.get(uid)
    name = display_name(user, lang)

    hint = DEEP_HINT if mode == "deep" else FAST_HINT
    prompt = f"(User's name: {name}. Reply in {lang}. {hint})\n\n{user_text}"
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
            tx(lang, "sorry") + CONTACT_TEXT, disable_web_page_preview=True
        )
        await send_owner(context, f"Alert: all models failed.\nError: {str(e)[:500]}")


# ---------- Handlers ----------
URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.I)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await notify_visitor(context, update.effective_user, text)

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
    lang = get_lang(uid)
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
        await msg.reply_text(tx(lang, "too_large", mb=MAX_FILE_MB))
        return

    lower = name.lower()
    supported = (
        lower.endswith((".pdf", ".txt", ".md", ".csv", ".docx", ".png", ".jpg", ".jpeg", ".webp"))
        or mime.startswith("image/")
    )
    if not supported:
        await msg.reply_text(tx(lang, "unsupported"))
        return

    await notify_visitor(context, update.effective_user, f"File: {name}\nCaption: {caption[:300]}")
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
        await msg.reply_text(tx(lang, "unreadable"))
        return

    user_files[uid] = info
    request = caption or tx(lang, "review_default")
    await respond(update, context, request, note=f"[File: {name}] ")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)
    await send_owner(context, f"Bot error: {str(context.error)[:500]}")


# ---------- Run ----------
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("expertise", expertise_cmd))
    app.add_handler(CommandHandler("contact", contact))
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