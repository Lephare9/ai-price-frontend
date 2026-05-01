from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from PIL import Image
import io
import os
import re
import json

print("🔥 APP STARTED")

app = FastAPI()

# 🌐 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔑 API key
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ---------- AI ----------
import base64

def analyze_image_with_ai(image_bytes):
    print("🔥 FUNCTION STARTED")

    try:
        prompt = """
Returnér KUN JSON:
{"name":"kort navn","price":123}
"""

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        print("🔥 CALLING AI...")

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }
            ]
        )

        print("🔥 AI CALLED")

        text = response.text
        print("🔥 AI RAW:", text)

        return text if text else '{"name":"ukendt","price":0}'

    except Exception as e:
        print("🔥 AI FEJL:", str(e))
        return '{"name":"ukendt","price":0}'

    return {"name": "ukendt", "price": 0}


# ---------- API ----------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    print("🔥 ENDPOINT HIT")

    image_bytes = await file.read()
    print("🔥 FILE RECEIVED:", len(image_bytes), "bytes")

    ai_response = analyze_image_with_ai(image_bytes)
    data = extract_json(ai_response)

    print("🔥 FINAL OUTPUT:", data)

    return {
        "description": data.get("name", "ukendt"),
        "price": data.get("price", 0)
    }


# ---------- TEST ----------
@app.get("/")
def root():
    return {"status": "ok"}