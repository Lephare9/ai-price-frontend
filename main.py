import os
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
import base64

print("🔥 AI PRICING AGENT v17 🔥")

# --- ENV ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    print("🔑 GEMINI: OK")
else:
    print("❌ GEMINI KEY MISSING")

# --- APP ---
app = FastAPI()

# --- CORS FIX ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # kan strammes senere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROOT ---
@app.get("/")
def root():
    return {"status": "ok", "version": "v17"}


# --- GEMINI FALLBACK ---
def call_gemini(client, image_bytes):
    models = [
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.0-pro"
    ]

    for model in models:
        try:
            print(f"⚡ TRY MODEL: {model}")

            response = client.models.generate_content(
                model=model,
                contents=[
                    "Hvad er dette objekt? Svar kort med navn.",
                    {
                        "mime_type": "image/jpeg",
                        "data": image_bytes
                    }
                ]
            )

            text = response.text.strip()
            print("🧠 GEMINI:", text)

            if text:
                return text

        except Exception as e:
            print(f"❌ FAIL {model}:", str(e))

    return None


# --- ANALYZE ---
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    print("=== /analyze ===")

    contents = await file.read()
    print(f"📷 SIZE: {len(contents)}")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Gemini call
        result = call_gemini(client, contents)

        if not result:
            return {
                "name": "Kunne ikke analysere billede",
                "price": 0,
                "results": []
            }

        return {
            "name": result,
            "price": 100,
            "results": []
        }

    except Exception as e:
        print("🚨 TOTAL FEJL:", str(e))
        return {
            "name": "Fejl",
            "price": 0,
            "results": []
        }