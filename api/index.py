import os
import re
import json
import asyncio
import anyio
from typing import List, Dict, Optional

from groq import Groq
from detoxify import Detoxify
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from transformers import pipeline
from mangum import Mangum
from moderate import app

# Create the Mangum handler for Vercel
handler = Mangum(app)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
tox_model = Detoxify("original")

# Initialize Groq API client
groq_client = None
groq_api_key = os.getenv("GROQ_API_KEY", os.environ.get("GROQ_API_KEY"))

if groq_api_key:
    try:
        groq_client = Groq(api_key=groq_api_key)
        print("✅ Groq API configured successfully")
    except Exception as e:
        print(f"⚠️ Groq API configuration failed: {e}")
        groq_client = None

# Local fallback model: T5-Paws
paraphrase_pipeline = pipeline(
    "text2text-generation",
    model="Vamsi/T5_Paraphrase_Paws",
    tokenizer="Vamsi/T5_Paraphrase_Paws"
)

class Message(BaseModel):
    text: str

def clean_rephrased_text(text: str) -> str:
    """Clean up AI-generated text by removing quotes, explanations, and prefixes."""
    text = text.strip()
    text = re.sub(r'^["\']|["\']$', '', text)
    text = re.sub(r'^\*\*|!\*\*$', '', text)
    
    prefixes_to_remove = [
        "Here's a polite version:",
        "Rewritten text:",
        "Polite version:",
        "Here is the rewritten text:",
        "The rewritten message is:",
        "POLITE VERSION:",
        "Rephrased:",
    ]
    
    for prefix in prefixes_to_remove:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
            text = re.sub(r'^[:;\-—]\s*', '', text)
    
    text = re.sub(r'^["\']|["\']$', '', text)
    return text.strip()

def is_valid_rephrasing(original: str, rephrased: str) -> bool:
    """Check if the rephrased text is valid and meaningful."""
    if not rephrased or len(rephrased) < 3:
        return False
    
    refusal_patterns = [
        "i cannot", "i can't", "i'm unable", "i am unable",
        "sorry", "apologize", "inappropriate",
        "i don't feel comfortable", "i cannot assist"
    ]
    
    rephrased_lower = rephrased.lower()
    if any(pattern in rephrased_lower for pattern in refusal_patterns):
        return False
    
    if rephrased.lower() == original.lower():
        return False
    
    return True

def create_generic_polite_message(original_text: str) -> str:
    """Create a context-aware polite message when rephrasing fails."""
    text_lower = original_text.lower()
    
    if any(word in text_lower for word in ["stupid", "dumb", "idiot", "moron"]):
        return "I don't think that's the best approach."
    elif any(word in text_lower for word in ["hate", "awful", "terrible", "worst"]):
        return "I'm not comfortable with this."
    elif any(word in text_lower for word in ["shut up", "shut", "quiet"]):
        return "I'd prefer if we could pause this conversation."
    elif any(word in text_lower for word in ["wrong", "disagree", "no"]):
        return "I have a different perspective on this."
    elif any(word in text_lower for word in ["ugly", "bad", "trash"]):
        return "I don't think this meets our standards."
    elif "?" in original_text:
        return "Could you help me understand this better?"
    else:
        return "I'd like to express this more constructively."

def local_paraphrase(text: str, max_length: int = 128) -> str:
    """Enhanced local fallback using T5 with context preservation."""
    try:
        input_text = f"rephrase politely while keeping the meaning: {text}"
        result = paraphrase_pipeline(
            input_text, 
            max_length=max_length, 
            num_return_sequences=1,
            do_sample=True,
            temperature=0.5
        )
        rephrased = result[0]['generated_text']
        rephrased = clean_rephrased_text(rephrased)
        
        if is_valid_rephrasing(text, rephrased):
            return rephrased
        return create_generic_polite_message(text)
    except Exception:
        return create_generic_polite_message(text)

def rephrase_with_groq(text: str) -> Optional[str]:
    """Rephrase text using Groq API (llama-3.3-70b-versatile)."""
    if not groq_client:
        return None
        
    try:
        prompt = f"""Rewrite this message to be polite and respectful while keeping the SAME meaning and context.

Rules:
- Keep the original intent and message
- Only make it polite and appropriate
- Keep it natural and conversational
- Output ONLY the rewritten text (no quotes, no explanations)

Original: "{text}"

Polite version:"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Fast and powerful
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that rephrases toxic messages to be polite while keeping their original meaning and context intact."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=150,
            top_p=0.9
        )
        
        if response.choices and len(response.choices) > 0:
            rephrased = clean_rephrased_text(response.choices[0].message.content)
            if is_valid_rephrasing(text, rephrased):
                return rephrased
        
        return None
    except Exception as e:
        print(f"Groq API error: {e}")
        return None

async def rephrase_logic(text: str) -> str:
    """Core rephrasing logic with Groq API primary, then local fallback."""
    # Try Groq API first
    result = await anyio.to_thread.run_sync(rephrase_with_groq, text)
    if result:
        return result
    
    # Fallback to local T5 model
    result = await anyio.to_thread.run_sync(local_paraphrase, text)
    return result

@app.post("/moderate")
async def moderate(msg: Message):
    text = msg.text.strip()
    tox_scores = await anyio.to_thread.run_sync(tox_model.predict, text)
    toxicity = float(tox_scores.get("toxicity", 0))

    if toxicity <= 0.5:
        return {"allowed": True, "score": round(toxicity, 3), "text": text}
    
    rephrased_text = await rephrase_logic(text)
    return {
        "allowed": False, 
        "score": round(toxicity, 3), 
        "original": text,
        "rephrased": rephrased_text
    }

@app.get("/")
async def root():
    return {
        "message": "Chat Toxicity Moderator API", 
        "status": "running", 
        "groq_configured": groq_client is not None,
        "model": "llama-3.3-70b-versatile"
    }

# Add Mangum adapter for serverless deployment
handler = Mangum(app)