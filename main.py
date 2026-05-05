from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os, base64, requests, json, re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERP_API_KEY = os.getenv("SERP_API_KEY")


# ---------- GEMINI (DEBUG + SAFE) ----------
def call_gemini(prompt, image):

    if not GEMINI_API_KEY:
        print("❌ NO GEMINI KEY")
        return None

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image
                    }
                }
            ]
        }]
    }

    try:
        r = requests.post(url, json=payload, timeout=12)

        print("🔍 GEMINI STATUS:", r.status_code)
        print("🔍 GEMINI RAW RESPONSE:", r.text[:1000])  # truncate

        if r.status_code != 200:
            return None

        data = r.json()

        if "candidates" not in data:
            print("❌ NO CANDIDATES FIELD")
            return None

        return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        print("❌ GEMINI EXCEPTION:", e)
        return None


# ---------- JSON ----------
def extract_json(text):

    if not text:
        return {}

    try:
        return json.loads(text)
    except:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])
        except:
            print("❌ JSON FAIL:", text)
            return {}


# ---------- IDENTIFY ----------
def identify(image):

    prompt = """
Identificér produkt.

Returnér JSON:
{
 "name": "",
 "brand": ""
}
"""

    raw = call_gemini(prompt, image)

    if raw is None:
        print("⚠️ GEMINI RETURNED NONE → FALLBACK")
        return {
            "name": "stol",
            "brand": ""
        }

    data = extract_json(raw)

    if not data or not data.get("name"):
        print("⚠️ EMPTY JSON → FALLBACK")
        return {
            "name": "stol",
            "brand": ""
        }

    print("✅ IDENTIFIED:", data)

    return data


# ---------- GOOGLE ----------
def google_prices(query):

    if not SERP_API_KEY:
        print("❌ NO SERP KEY")
        return []

    url = "https://serpapi.com/search"

    params = {
        "q": query,
        "api_key": SERP_API_KEY,
        "hl": "da",
        "gl": "dk"
    }

    prices = []

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        for res in data.get("organic_results", []):
            text = (res.get("title", "") + " " + res.get("snippet", "")).lower()

            matches = re.findall(r"(\d{2,5})\s*kr", text)

            for m in matches:
                val = int(m)
                if 20 < val < 50000:
                    prices.append(val)

    except Exception as e:
        print("❌ SEARCH ERROR:", e)

    print("💰 RAW PRICES:", prices[:10])

    return prices


# ---------- FILTER ----------
def filter_prices(prices):

    if not prices:
        return []

    prices = sorted(prices)
    mid = prices[len(prices)//2]

    filtered = [p for p in prices if mid*0.6 < p < mid*1.8]

    print("🔎 FILTERED:", filtered)

    return filtered


# ---------- API ----------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):

    img = await file.read()

    print("📸 IMAGE SIZE:", len(img))

    if not img:
        return {
            "description": "ingen fil modtaget",
            "price_range": "ingen pris"
        }

    img64 = base64.b64encode(img).decode("utf-8")

    data = identify(img64)

    name = data.get("name", "")
    brand = data.get("brand", "")

    query = f"{name} stol brugt pris"

    print("🔍 QUERY:", query)

    prices = google_prices(query)

    if not prices:
        prices = google_prices(name)

    prices = filter_prices(prices)

    if len(prices) >= 2:
        avg = sum(prices) / len(prices)
        low = int(avg * 0.9)
        high = int(avg * 1.1)
    else:
        low, high = 100, 500

    return {
        "description": f"{name}\n{brand}",
        "price_range": f"{low} - {high} kr"
    }


@app.get("/")
def root():
    return {"status": "ok", "mode": "v15.2-debug"}