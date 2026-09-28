import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from pydantic import BaseModel

ai_client = genai.Client()

class GrievanceAnalysis(BaseModel):
    category: str
    urgency_score: int
    ai_summary: str

prompt = "Analyze the following civic grievance. Determine the category (e.g., 'Road Infrastructure', 'Water Supply', 'Electricity', 'Sanitation'), assign an urgency score from 1 to 5 (5 being critical/safety hazard), and provide a 1-sentence ai_summary.\n\nGrievance: There is a huge pothole on Main Street that is causing severe accidents."

try:
    response = ai_client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt,
        config={'response_mime_type': 'application/json', 'response_schema': GrievanceAnalysis, 'temperature': 0.1}
    )
    print(response.parsed)
except Exception as e:
    import traceback
    traceback.print_exc()
