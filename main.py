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


# ---------- GEMINI ----------
def call_gemini(prompt, image):

    if not GEMINI_API_KEY:
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
        r = requests.post(url, json=payload, timeout=10)

        if r.status_code != 200:
            print("GEMINI HTTP ERROR")
            return None

        data = r.json()

        if "candidates" not in data:
            print("NO CANDIDATES")
            return None

        return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        print("GEMINI FAIL:", e)
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
            return {}


# ---------- IDENTIFY ----------
def identify(image):

    prompt = """
Identificér produkt (kort).

Returnér JSON:
{
 "name": "",
 "brand": ""
}
"""

    raw = call_gemini(prompt, image)

    # 🔥 hvis Gemini fejler → HARD fallback
    if raw is None:
        print("GEMINI FAIL → USING DEFAULT")
        return {
            "name": "stol",
            "brand": ""
        }

    data = extract_json(raw)

    if not data or not data.get("name"):
        return {
            "name": "stol",
            "brand": ""
        }

    return data


# ---------- GOOGLE ----------
def google_prices(query):

    if not SERP_API_KEY:
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

    except:
        pass

    return prices


# ---------- FILTER ----------
def filter_prices(prices):

    if not prices:
        return []

    prices = sorted(prices)
    mid = prices[len(prices)//2]

    return [p for p in prices if mid*0.6 < p < mid*1.8]


# ---------- API ----------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):

    img = await file.read()
    img64 = base64.b64encode(img).decode()

    data = identify(img64)

    name = data.get("name", "")
    brand = data.get("brand", "")

    # 🔥 altid brug simpelt query (mere stabil)
    query = f"{name} stol brugt pris"

    prices = google_prices(query)

    if not prices:
        prices = google_prices(name)

    prices = filter_prices(prices)

    if len(prices) >= 2:
        avg = sum(prices)/len(prices)
        low = int(avg*0.9)
        high = int(avg*1.1)
    else:
        low, high = 100, 500

    return {
        "description": f"{name}\n{brand}",
        "price_range": f"{low} - {high} kr",
        "condition": "",
        "note": ""
    }


@app.get("/")
def root():
    return {"status": "ok"}