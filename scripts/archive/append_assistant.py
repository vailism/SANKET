import sys
import os

with open('sanket/api.py', 'a') as f:
    f.write('''
class AssistantRequest(BaseModel):
    message: str
    context: Dict[str, Any]

class AssistantKeyRequest(BaseModel):
    key: str

@app.post("/api/assistant")
def assistant_chat(payload: AssistantRequest) -> Dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return JSONResponse(status_code=503, content={"error": True, "message": "SANKET Analyst is offline — GEMINI_API_KEY is not configured. Copy .env.example to .env and add your key."})
    
    if not payload.message or not payload.message.strip():
        return JSONResponse(status_code=400, content={"error": True, "message": "Message is required."})
    
    if len(payload.message) > 2000:
        return JSONResponse(status_code=400, content={"error": True, "message": "Message exceeds 2 000 character limit."})

    try:
        from google import genai
        from google.genai import types
        import json
        
        client = genai.Client(api_key=api_key)
        
        system_instruction = (
            "You are the SANKET Analyst Assistant — a concise, data-driven infrastructure-risk analyst embedded in the SANKET command-center dashboard.\\n\\n"
            "RULES:\\n"
            "1. Base every claim on the dashboard context supplied below. Cite specific metrics (e.g., \\"Score 92/100\\", \\"−27.3 % MoRTH discrepancy\\").\\n"
            "2. Clearly distinguish hard data from inference. Use phrases like \\"Data shows…\\" vs \\"This suggests…\\".\\n"
            "3. Never fabricate statistics, project names, or sensor readings that are not in the context.\\n"
            "4. When a critical threshold is exceeded (score >= 90, variance > 15 %, stagnation > 30 days) recommend escalation and cite the relevant protocol (Sec. 14 Notice, Emergency Dispatch).\\n"
            "5. Keep answers compact — aim for 3-6 sentences unless the user asks for detail.\\n"
            "6. Use professional, government-operations tone. No emojis.\\n\\n"
            f"DASHBOARD CONTEXT (live snapshot):\\n{json.dumps(payload.context, indent=2)}"
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=payload.message,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
        
        return {"reply": response.text}
    except Exception as e:
        msg = str(e)
        if "429" in msg or "quota" in msg.lower():
            return JSONResponse(status_code=429, content={"error": True, "message": "Rate limit reached. Please wait a moment before retrying."})
        return JSONResponse(status_code=500, content={"error": True, "message": "SANKET Analyst encountered an internal error. Please retry."})

@app.post("/api/assistant/key")
def assistant_set_key(payload: AssistantKeyRequest) -> Dict[str, Any]:
    if payload.key:
        os.environ["GEMINI_API_KEY"] = payload.key
        return {"success": True}
    return JSONResponse(status_code=400, content={"error": True})
''')
