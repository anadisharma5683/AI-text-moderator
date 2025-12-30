"""
FastAPI application for AI-powered text moderation with toxicity detection and rephrasing.
Uses Detoxify for toxicity analysis, Groq API for primary rephrasing, and T5 as fallback.
"""

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
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from transformers import pipeline
import uvicorn

# Load environment variables
load_dotenv()

# Initialize FastAPI application
app = FastAPI(title="AI Text Moderator", description="Real-time content moderation with AI-powered rephrasing")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Initialize toxicity detection model
tox_model = Detoxify("original")

# Initialize Groq API client (if key is available)
groq_client = None
groq_api_key = os.getenv("GROQ_API_KEY")

if groq_api_key and groq_api_key.strip():
    try:
        groq_client = Groq(api_key=groq_api_key)
        print("✅ Groq API configured and ready")
    except Exception as error:
        print(f"⚠️ Failed to initialize Groq API: {error}")
        groq_client = None
else:
    print("⚠️ GROQ_API_KEY not found in environment - using local fallback only")

# Initialize local T5 paraphrasing pipeline as fallback
paraphrase_pipeline = pipeline(
    "text2text-generation",
    model="Vamsi/T5_Paraphrase_Paws",
    tokenizer="Vamsi/T5_Paraphrase_Paws",
)

# Toxicity threshold
TOXICITY_THRESHOLD = 0.5


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages to all active clients."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection from the active list."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: str):
        """Send a message to all active connections, removing failed ones."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up failed connections
        for conn in disconnected:
            self.disconnect(conn)


# Create connection managers for different WebSocket endpoints
chat_manager = ConnectionManager()
moderator_manager = ConnectionManager()


# ============================================================================
# Pydantic Models
# ============================================================================

class Message(BaseModel):
    """Request model for text messages."""
    text: str


# ============================================================================
# Helper Functions - Text Cleaning and Validation
# ============================================================================

def clean_rephrased_text(text: str) -> str:
    """
    Clean rephrased text by removing common prefixes, quotes, and extra whitespace.
    
    Args:
        text: The rephrased text to clean
        
    Returns:
        Cleaned text string
    """
    cleaned = text.strip()
    
    # Remove common prefixes that LLMs add
    prefixes_to_remove = [
        "Here's a polite version:",
        "Rephrased:",
        "Polite version:",
        "Here's the polite version:",
        "Rewritten:",
        "Polite:",
        "Here is a polite version:",
        "Here is the polite version:",
    ]
    
    for prefix in prefixes_to_remove:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
    
    # Remove surrounding quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or \
       (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    
    return cleaned


def is_valid_rephrasing(original: str, rephrased: str) -> bool:
    """
    Validate that a rephrased text is acceptable.
    
    Args:
        original: The original toxic text
        rephrased: The rephrased version
        
    Returns:
        True if rephrasing is valid, False otherwise
    """
    # Check minimum length
    if len(rephrased) < 5:
        return False
    
    # Check for refusal patterns
    refusal_patterns = [
        "i cannot",
        "i can't",
        "sorry",
        "inappropriate",
        "unable to",
        "i'm unable",
        "not appropriate",
        "against policy",
        "i apologize",
    ]
    
    rephrased_lower = rephrased.lower()
    for pattern in refusal_patterns:
        if pattern in rephrased_lower:
            return False
    
    # Check if identical to original (case-insensitive)
    if original.strip().lower() == rephrased.strip().lower():
        return False
    
    return True


def create_generic_polite_message(original_text: str) -> str:
    """
    Create a context-aware generic polite message based on the original text.
    
    Args:
        original_text: The original toxic message
        
    Returns:
        A generic but contextually appropriate polite message
    """
    text_lower = original_text.lower()
    
    # Detect context and provide appropriate fallback
    if any(word in text_lower for word in ["stupid", "idiot", "dumb", "moron"]):
        return "I respectfully disagree with that perspective."
    
    if any(word in text_lower for word in ["hate", "disgusting", "terrible"]):
        return "I understand there may be strong feelings about this, but let's keep the discussion respectful."
    
    if any(word in text_lower for word in ["shut up", "quiet", "be silent"]):
        return "I'd prefer if we could have a constructive conversation."
    
    if any(word in text_lower for word in ["ugly", "gross", "hideous"]):
        return "I don't think that kind of comment is helpful here."
    
    if any(word in text_lower for word in ["loser", "failure", "worthless"]):
        return "Everyone has value and deserves to be treated with respect."
    
    # Generic fallback
    return "I'd like to express this in a more constructive way."


def local_paraphrase(text: str, max_length: int = 128) -> str:
    """
    Use local T5 model to paraphrase text into a polite version.
    
    Args:
        text: The text to paraphrase
        max_length: Maximum length of generated text
        
    Returns:
        Paraphrased polite version of the text
    """
    try:
        # Craft prompt for T5 model
        prompt = f"paraphrase: {text}"
        
        # Generate paraphrase
        result = paraphrase_pipeline(
            prompt,
            max_length=max_length,
            num_return_sequences=1,
            temperature=0.7,
        )
        
        # Extract and clean the output
        paraphrased = result[0]["generated_text"]
        cleaned = clean_rephrased_text(paraphrased)
        
        # Validate the result
        if is_valid_rephrasing(text, cleaned):
            return cleaned
        else:
            return create_generic_polite_message(text)
            
    except Exception as error:
        print(f"Error in local paraphrase: {error}")
        return create_generic_polite_message(text)


def rephrase_with_groq(text: str) -> Optional[str]:
    """
    Use Groq API to rephrase toxic text into a polite version.
    
    Args:
        text: The toxic text to rephrase
        
    Returns:
        Rephrased text if successful, None otherwise
    """
    if groq_client is None:
        return None
    
    try:
        # Create chat completion request
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a text moderation assistant. Your task is to rephrase toxic, "
                        "offensive, or inappropriate messages into polite, respectful versions "
                        "while preserving the core meaning and context. Output ONLY the rephrased "
                        "text without any explanations, prefixes, or additional commentary."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Rewrite the following message to be polite and respectful while "
                        f"keeping its meaning and context. Output only the rewritten text:\n\n{text}"
                    )
                }
            ],
            temperature=0.7,
            max_tokens=150,
        )
        
        # Extract and clean the response
        rephrased = completion.choices[0].message.content
        cleaned = clean_rephrased_text(rephrased)
        
        # Validate the rephrasing
        if is_valid_rephrasing(text, cleaned):
            return cleaned
        else:
            return None
            
    except Exception as error:
        print(f"Error with Groq API: {error}")
        return None


async def rephrase_logic(text: str) -> str:
    """
    Main rephrasing logic: try Groq API first, fall back to local T5 model.
    
    Args:
        text: The toxic text to rephrase
        
    Returns:
        Rephrased polite version of the text
    """
    # Try Groq API first (if available)
    if groq_client is not None:
        groq_result = await anyio.to_thread.run_sync(rephrase_with_groq, text)
        if groq_result is not None:
            return groq_result
    
    # Fall back to local T5 model
    local_result = await anyio.to_thread.run_sync(local_paraphrase, text)
    return local_result


# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.post("/moderate")
async def moderate_text(message: Message):
    """
    Moderate a text message for toxicity and rephrase if needed.
    
    Args:
        message: Message object containing text to moderate
        
    Returns:
        JSON response with moderation results
    """
    text = message.text.strip()
    
    # Predict toxicity using Detoxify model
    toxicity_scores = await anyio.to_thread.run_sync(tox_model.predict, text)
    toxicity_score = float(toxicity_scores.get("toxicity", 0.0))
    
    # Check if text is acceptable
    if toxicity_score <= TOXICITY_THRESHOLD:
        return {
            "allowed": True,
            "score": round(toxicity_score, 3),
            "text": text
        }
    
    # Text is toxic - rephrase it
    rephrased_text = await rephrase_logic(text)
    
    return {
        "allowed": False,
        "score": round(toxicity_score, 3),
        "original": text,
        "rephrased": rephrased_text
    }


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with moderation.
    
    Receives messages, checks toxicity, and broadcasts to all connected clients.
    """
    await chat_manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Extract message content and username
            text = message_data.get("text", "")
            username = message_data.get("username", "Anonymous")
            
            # Analyze toxicity
            toxicity_scores = await anyio.to_thread.run_sync(tox_model.predict, text)
            toxicity_score = float(toxicity_scores.get("toxicity", 0.0))
            
            # Get timestamp
            timestamp = asyncio.get_event_loop().time()
            
            # Build response object
            response = {
                "username": username,
                "original_text": text,
                "toxicity": round(toxicity_score, 3),
                "timestamp": timestamp
            }
            
            # Determine if message should be moderated
            if toxicity_score <= TOXICITY_THRESHOLD:
                response["allowed"] = True
                response["display_text"] = text
            else:
                # Rephrase toxic message
                rephrased_text = await rephrase_logic(text)
                response["allowed"] = False
                response["display_text"] = rephrased_text
                response["original_displayed"] = False
            
            # Broadcast to all connected chat clients
            await chat_manager.broadcast(json.dumps(response))
            
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket)


@app.websocket("/ws/moderator")
async def websocket_moderator_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for moderator view.
    
    Receives messages, checks toxicity, and broadcasts moderation details to moderators.
    """
    await moderator_manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Extract message content
            text = message_data.get("text", "")
            
            # Analyze toxicity
            toxicity_scores = await anyio.to_thread.run_sync(tox_model.predict, text)
            toxicity_score = float(toxicity_scores.get("toxicity", 0.0))
            
            # Determine if moderation is needed
            moderated = toxicity_score >= TOXICITY_THRESHOLD
            
            # Get final text (rephrase if moderated)
            if moderated:
                final_text = await rephrase_logic(text)
            else:
                final_text = text
            
            # Build moderator response
            moderator_response = {
                "original": text,
                "final": final_text,
                "toxicity": round(toxicity_score, 3),
                "moderated": moderated
            }
            
            # Broadcast to all connected moderator clients
            await moderator_manager.broadcast(json.dumps(moderator_response))
            
    except WebSocketDisconnect:
        moderator_manager.disconnect(websocket)


# ============================================================================
# HTML Template Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    """Serve the main moderator page at root."""
    return templates.TemplateResponse("moderator.html", {"request": request})


@app.get("/moderator")
async def moderator_page(request: Request):
    """Serve the moderator interface page."""
    return templates.TemplateResponse("moderator.html", {"request": request})


@app.get("/demo")
async def demo_page(request: Request):
    """Serve the demo page."""
    return templates.TemplateResponse("demo.html", {"request": request})


@app.get("/sender")
async def sender_page(request: Request):
    """Serve the sender interface page."""
    return templates.TemplateResponse("sender.html", {"request": request})


@app.get("/receiver")
async def receiver_page(request: Request):
    """Serve the receiver interface page."""
    return templates.TemplateResponse("receiver.html", {"request": request})


# ============================================================================
# Application Startup
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Starting AI Text Moderator Service")
    print("="*60)
    
    if groq_client:
        print("✅ Groq API: Configured (Primary rephrasing)")
    else:
        print("⚠️  Groq API: Not configured (Using local T5 fallback only)")
    
    print(f"✅ Local T5 Model: Ready (Fallback rephrasing)")
    print(f"✅ Detoxify Model: Loaded (Toxicity detection)")
    print(f"🌐 Server starting on http://0.0.0.0:8000")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
