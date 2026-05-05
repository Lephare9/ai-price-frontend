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


# ---------- GEMINI (RETRY) ----------
def call_gemini(prompt, image=None):

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    parts = [{"text": prompt}]
    if image:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image
            }
        })

    payload = {"contents": [{"parts": parts}]}

    for i in range(3):
        try:
            r = requests.post(url, json=payload, timeout=15)
            data = r.json()

            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"]

            print("GEMINI FAIL:", data)

        except Exception as e:
            print("ERROR:", e)

    return None


# ---------- JSON FIX ----------
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
            print("JSON FAIL:", text)
            return {}


# ---------- IDENTIFY ----------
def identify(image):

    prompt = """
Identificér produkt.

Returnér KUN JSON:
{
 "name": "",
 "brand": "",
 "model": "",
 "category": "",
 "material": "",
 "shape": "",
 "style": ""
}
"""

    raw = call_gemini(prompt, image)
    print("RAW GEMINI:", raw)

    data = extract_json(raw)

    # 🔥 fallback (ALDRIG tom)
    if not data or not data.get("name"):
        print("IDENTIFY FALLBACK")
        return {
            "name": "stol",
            "brand": "",
            "category": "furniture"
        }

    # fallback brand
    if not data.get("brand") and data.get("name"):
        data["brand"] = data["name"].split()[0]

    # model boost
    if data.get("brand") and data.get("model"):
        data["name"] = f"{data['brand']} {data['model']}"

    print("FINAL DATA:", data)

    return data


# ---------- BUILD QUERY ----------
def build_query(data):

    parts = []

    for key in ["brand", "name", "material", "shape", "style"]:
        if data.get(key):
            parts.append(data[key])

    parts.append("brugt pris danmark")

    query = " ".join(parts)

    print("QUERY:", query)

    return query


# ---------- GOOGLE ----------
def google_search(query):

    url = "https://serpapi.com/search"

    params = {
        "q": query,
        "api_key": SERP_API_KEY,
        "hl": "da",
        "gl": "dk"
    }

    try:
        r = requests.get(url, params=params)
        data = r.json()

        prices = []

        for res in data.get("organic_results", []):
            text = (res.get("title", "") + " " + res.get("snippet", "")).lower()

            matches = re.findall(r"(\d{2,5})[\s.,-]*kr", text)

            for m in matches:
                val = int(m)
                if 20 < val < 50000:
                    prices.append(val)

        print("GOOGLE PRICES:", prices[:10])

        return prices

    except Exception as e:
        print("GOOGLE ERROR:", e)
        return []


# ---------- FILTER ----------
def smart_filter(prices, brand):

    if not prices:
        return []

    prices = sorted(prices)
    median = prices[len(prices)//2]

    filtered = []

    for p in prices:
        if p < median * 0.4:
            continue
        if p > median * 2.5:
            continue
        filtered.append(p)

    if brand:
        filtered = [p for p in filtered if p > median * 0.6]

    print("FILTERED:", filtered)

    return filtered


# ---------- CALC ----------
def round5(x):
    return int(round(x / 5) * 5)


def calc(prices):

    if len(prices) < 2:
        return None

    avg = sum(prices) / len(prices)

    return round5(avg * 0.9), round5(avg * 1.1)


# ---------- API ----------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):

    img = await file.read()
    img64 = base64.b64encode(img).decode()

    data = identify(img64)

    name = data.get("name", "")
    brand = data.get("brand", "")
    category = data.get("category", "")
    condition = data.get("condition", "")

    # 🔴 blokér
    if category in ["vehicle", "electronics"]:
        return {
            "description": f"{name}\n{brand}",
            "price_range": "Ikke understøttet",
            "condition": condition,
            "note": ""
        }

    query = build_query(data)

    prices = google_search(query)

    # fallback søgning
    if not prices:
        print("FALLBACK SEARCH")
        prices = google_search(name + " brugt pris")

    prices = smart_filter(prices, brand)

    result = calc(prices)

    # 🔥 sidste fallback (ALDRIG tom)
    if not result:
        if brand:
            result = (1500, 3500)
        else:
            result = (100, 500)

    min_p, max_p = result

    return {
        "description": f"{name}\n{brand}",
        "price_range": f"{min_p} - {max_p} kr",
        "condition": condition,
        "note": ""
    }


@app.get("/")
def root():
    return {"status": "ok", "mode": "v15.1-stable"}