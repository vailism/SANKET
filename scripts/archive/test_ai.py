import os
import json
from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

system_instruction = "You are an assistant."
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="hello",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        )
    )
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
