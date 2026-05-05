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


# ---------- GEMINI (ROBUST) ----------
def call_gemini(prompt, image=None):

    if not GEMINI_API_KEY:
        print("NO GEMINI KEY")
        return None

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

    for i in range(2):  # 🔥 retry
        try:
            r = requests.post(url, json=payload, timeout=12)

            if r.status_code != 200:
                print("GEMINI HTTP ERROR:", r.text)
                continue

            data = r.json()

            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"]

            print("GEMINI BAD STRUCT:", data)

        except Exception as e:
            print("GEMINI EXCEPTION:", e)

    return None


# ---------- JSON SAFE ----------
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
Identificér produkt præcist.

Returnér JSON:
{
 "name": "",
 "brand": "",
 "category": ""
}
"""

    raw = call_gemini(prompt, image)
    print("RAW GEMINI:", raw)

    data = extract_json(raw)

    # 🔥 FAILSAFE
    if not data or not data.get("name"):
        print("IDENTIFY FALLBACK")
        return {
            "name": "stol",
            "brand": "",
            "category": "furniture"
        }

    # fallback brand
    if not data.get("brand"):
        words = data["name"].split()
        if len(words) > 1:
            data["brand"] = words[0]

    print("IDENTIFIED:", data)

    return data


# ---------- QUERY ----------
def build_query(data):

    name = data.get("name", "")
    brand = data.get("brand", "")

    if brand:
        query = f"{brand} {name} stol brugt pris danmark"
    else:
        query = f"{name} stol brugt pris danmark"

    print("QUERY:", query)

    return query


# ---------- GOOGLE ----------
def google_search(query):

    if not SERP_API_KEY:
        print("NO SERP KEY")
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

            matches = re.findall(r"(\d{2,5})[\s.,-]*kr", text)

            for m in matches:
                val = int(m)
                if 20 < val < 50000:
                    prices.append(val)

    except Exception as e:
        print("SEARCH ERROR:", e)

    print("RAW PRICES:", prices[:10])

    return prices


# ---------- FILTER ----------
def smart_filter(prices):

    if len(prices) < 3:
        return prices

    prices = sorted(prices)
    median = prices[len(prices)//2]

    filtered = []

    for p in prices:
        if p < median * 0.5:
            continue
        if p > median * 2:
            continue
        filtered.append(p)

    if len(filtered) > 5:
        cut = int(len(filtered) * 0.2)
        filtered = filtered[cut:]

    print("FILTERED:", filtered)

    return filtered


# ---------- CALC ----------
def calc_price(prices):

    if len(prices) < 2:
        return None

    avg = sum(prices) / len(prices)

    low = int(avg * 0.9)
    high = int(avg * 1.1)

    return low, high


# ---------- API ----------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):

    img = await file.read()
    img64 = base64.b64encode(img).decode()

    data = identify(img64)

    name = data.get("name", "")
    brand = data.get("brand", "")
    category = data.get("category", "")

    # 🔴 BLOCK
    if category in ["vehicle", "electronics"]:
        return {
            "description": f"{name}\n{brand}",
            "price_range": "Ikke understøttet",
            "condition": "",
            "note": ""
        }

    query = build_query(data)

    prices = google_search(query)

    # fallback søgning
    if not prices:
        print("FALLBACK SEARCH")
        prices = google_search(name + " brugt pris")

    filtered = smart_filter(prices)

    result = calc_price(filtered)

    # 🔥 FINAL FAILSAFE
    if not result:
        if filtered:
            avg = sum(filtered) / len(filtered)
            result = (int(avg * 0.8), int(avg * 1.2))
        else:
            result = (100, 500)

    return {
        "description": f"{name}\n{brand}",
        "price_range": f"{result[0]} - {result[1]} kr",
        "condition": "",
        "note": ""
    }


@app.get("/")
def root():
    return {"status": "ok", "mode": "v15.2-robust"}