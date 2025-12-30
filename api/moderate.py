import os
import re
from typing import Optional
from pydantic import BaseModel
from mangum import Mangum
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# Simple keyword-based toxicity detection for Vercel compatibility
def simple_toxicity_detection(text: str) -> float:
    """Simple keyword-based toxicity detection."""
    toxic_keywords = [
        "idiot", "stupid", "dumb", "moron", "hate", "kill", "murder", 
        "hate", "awful", "terrible", "worst", "ugly", "stupid", "dumb", "fuck",
        "shit", "bitch", "asshole", "dick", "pussy", "cunt", "nigger", "fag"
    ]
    
    text_lower = text.lower()
    toxic_count = sum(1 for word in toxic_keywords if word in text_lower)
    
    # Calculate a simple score based on toxic word density
    if toxic_count == 0:
        return 0.0
    elif toxic_count == 1:
        return 0.4
    elif toxic_count == 2:
        return 0.6
    elif toxic_count == 3:
        return 0.7
    else:
        return min(0.9, 0.6 + (toxic_count * 0.1))

async def rephrase_with_groq(text: str) -> Optional[str]:
    """Rephrase text using Groq API if available."""
    # Since we're optimizing for minimal build, skip external API calls
    # This function is effectively disabled in minimal config
    # to prevent build-time dependencies issues
    return None

@app.post("/moderate")
async def moderate(msg: Message):
    text = msg.text.strip()
    
    # Use simple toxicity detection for Vercel compatibility
    toxicity = simple_toxicity_detection(text)
    
    if toxicity <= 0.5:
        return {"allowed": True, "score": round(toxicity, 3), "text": text}
    
    # Try to rephrase using Groq API if available, otherwise use generic message
    rephrased_text = await rephrase_with_groq(text)
    if not rephrased_text:
        rephrased_text = create_generic_polite_message(text)
    
    return {
        "allowed": False, 
        "score": round(toxicity, 3), 
        "original": text,
        "rephrased": rephrased_text
    }

@app.get("/")
async def root():
    return {
        "message": "Chat Toxicity Moderator API (Minimal Vercel Config)", 
        "status": "running",
        "model": "keyword-based detection"
    }

# Create the Mangum handler for Vercel
handler = Mangum(app)