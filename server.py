import os
import io
import requests
from dotenv import load_dotenv
from PIL import Image
from database import history_collection
from datetime import datetime
import base64

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

# =========================================================
# 1. APP SETUP
# =========================================================

app = FastAPI(title="MedRAX AI – BLIP + GROQ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

# =========================================================
# 2. GROQ CONFIG
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# =========================================================
# 3. LOAD BLIP (IMAGE → TEXT)
# =========================================================

device = "cuda" if torch.cuda.is_available() else "cpu"

blip_processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-large"
)
blip_model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-large"
).to(device)

blip_model.eval()

# =========================================================
# 4. IMAGE → CAPTION
# =========================================================

def get_image_caption(image: Image.Image) -> str:
    inputs = blip_processor(
        image,
        "Describe radiographic findings in this pediatric chest X-ray",
        return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        out = blip_model.generate(**inputs, max_new_tokens=200,num_beams=5,
    repetition_penalty=1.2)

    return blip_processor.decode(out[0], skip_special_tokens=True)

# =========================================================
# 5. CAPTION → LONG REPORT (GROQ)
# =========================================================

def generate_long_report_with_groq(caption: str) -> str:
    prompt = f"""
You are a senior radiologist.

TASK:
Generate a DETAILED chest X-ray radiology report of AT LEAST 400 WORDS
(half to three-quarter page).

STRICT RULES:
- Minimum length: 400 words
- Write full paragraphs (NO headings-only)
- Professional radiology language
- Expand EACH section clearly
- If findings are normal, explain WHY
- Do NOT hallucinate anatomy
- No treatment advice

SECTIONS (expand all):
Examination
Technique
Image Quality
Lung Fields
Cardiac Silhouette
Mediastinum and Hila
Pleura
Bones and Soft Tissues
Impression (numbered)
Recommendations

Image description:
{caption}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a medical imaging assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.25,
        "max_tokens": 1800
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(response.text)

    result = response.json()
    
    if response.status_code != 200:
        print("GROQ ERROR:", result)
        raise RuntimeError("Groq API failed")

    if "choices" not in result:
        print("GROQ INVALID RESPONSE:", result)
        raise RuntimeError("No response generated")

    return result["choices"][0]["message"]["content"]


# =========================================================
# 6. MAIN ENDPOINT (USED BY FRONTEND)
# =========================================================

"""@app.post("/analyze-image/")
async def analyze_image_endpoint(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Not an image")

    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    caption = get_image_caption(image)
    report = generate_long_report_with_groq(caption)

    return {"analysis": report}"""

@app.post("/analyze-image/")
async def analyze_image_endpoint(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Not an image")

    image_bytes = await file.read()

    # Convert image to base64 (BEST for MongoDB)
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    caption = get_image_caption(image)
    report = generate_long_report_with_groq(caption)

    # 🔹 SAVE TO MONGODB
    history_doc = {
        "image_base64": image_base64,
        "caption": caption,
        "report": report,
        "qa_history": [],
        "created_at": datetime.utcnow()
    }

    inserted = history_collection.insert_one(history_doc)

    return {
        "analysis": report,
        "history_id": str(inserted.inserted_id)
    }


# =========================================================
# 7. FOLLOW-UP Q&A (TEXT ONLY, GROQ)
# =========================================================

""" @app.post("/ask/")
async def ask_question(request: Request):
    data = await request.json()
    question = data.get("question")
    report = data.get("report")

    if not question or not report:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing input"}
        )

  # prompt =  f"""
#You are a medical assistant.

#Answer strictly based on the report below.
#If the answer is not present, say:
#"The report does not provide sufficient information."

#REPORT:
#{report}

#QUESTION:
#{question}
"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 800
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload)

    try:
        result = response.json()
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": "Invalid response from Groq"}
        )

    if response.status_code != 200 or "choices" not in result:
        print("GROQ /ask ERROR:", result)
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to generate answer"}
        )

    answer = result["choices"][0]["message"]["content"]
    return {"text": answer}
"""
from bson import ObjectId

@app.post("/ask/")
async def ask_question(request: Request):
    data = await request.json()

    history_id = data.get("history_id")
    question = data.get("question")

    if not history_id or not question:
        return JSONResponse(status_code=400, content={"error": "Missing data"})

    record = history_collection.find_one({"_id": ObjectId(history_id)})

    if not record:
        return JSONResponse(status_code=404, content={"error": "History not found"})

    report = record["report"]

    prompt = f"""
Answer the question strictly using the report.

REPORT:
{report}

QUESTION:
{question}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 700
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload)
    answer = response.json()["choices"][0]["message"]["content"]

    # 🔹 SAVE Q&A
    history_collection.update_one(
        {"_id": ObjectId(history_id)},
        {
            "$push": {
                "qa_history": {
                    "question": question,
                    "answer": answer,
                    "time": datetime.utcnow()
                }
            }
        }
    )

    return {"text": answer}


# =========================================================
# 8. ROOT
# =========================================================

@app.get("/")
def root():
    return {"message": "MedRAX AI running with BLIP + GROQ"}

@app.get("/history/")
def get_history():
    records = list(history_collection.find().sort("created_at", -1))

    for r in records:
        r["_id"] = str(r["_id"])

    return records

