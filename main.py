import os
import logging
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import requests

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-pricing-agent")

logger.info("🔥 AI PRICING AGENT v1 STARTING")

# =========================
# ENV
# =========================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY missing")

if not SERPAPI_KEY:
    logger.error("❌ SERPAPI_KEY missing")

genai.configure(api_key=GEMINI_API_KEY)

# =========================
# APP
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # sæt din Netlify URL senere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ROOT
# =========================
@app.get("/")
def root():
    return {"status": "ok", "version": "v1"}

# =========================
# HELPER: GEMINI
# =========================
def detect_object(image_bytes: bytes, mime_type: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")

        response = model.generate_content([
            {
                "mime_type": mime_type,
                "data": image_bytes
            },
            "Identify the object in this image. Return ONLY 1-3 words. No sentence."
        ])

        text = (response.text or "").strip().lower()

        if not text or len(text) > 40:
            logger.warning(f"⚠️ Bad Gemini output: {text}")
            return "genstand"

        return text

    except Exception as e:
        logger.error(f"🚨 GEMINI ERROR: {str(e)}")
        raise


# =========================
# HELPER: SERPAPI
# =========================
def fetch_prices(query: str):
    try:
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": SERPAPI_KEY
        }

        r = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=10
        )

        if r.status_code != 200:
            logger.error(f"SERPAPI HTTP {r.status_code}")
            return []

        data = r.json()

        prices = []

        for item in data.get("shopping_results", []):
            raw = item.get("price")
            if not raw:
                continue

            digits = "".join(c for c in raw if c.isdigit())
            if digits:
                prices.append(int(digits))

        return prices

    except Exception as e:
        logger.error(f"🚨 SERPAPI ERROR: {str(e)}")
        return []


# =========================
# ANALYZE
# =========================
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    logger.info("=== /analyze ===")

    try:
        image_bytes = await file.read()

        if not image_bytes:
            return {
                "title": "Ingen fil",
                "price": 0,
                "results": []
            }

        logger.info(f"📷 SIZE: {len(image_bytes)} bytes")
        logger.info(f"📷 MIME: {file.content_type}")

        # =========================
        # GEMINI
        # =========================
        try:
            title = detect_object(image_bytes, file.content_type)
            logger.info(f"🧠 OBJECT: {title}")

        except Exception:
            return {
                "title": "Kunne ikke analysere",
                "price": 0,
                "results": []
            }

        # =========================
        # SERPAPI
        # =========================
        prices = fetch_prices(f"{title} used price")

        logger.info(f"💰 PRICES: {prices}")

        if prices:
            avg_price = int(sum(prices) / len(prices))
        else:
            avg_price = 0

        # =========================
        # RESPONSE
        # =========================
        return {
            "title": title,
            "price": avg_price,
            "results": prices
        }

    except Exception as e:
        logger.error(f"🔥 CRASH: {str(e)}")

        return {
            "title": "Server fejl",
            "price": 0,
            "results": []
        }