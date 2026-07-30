import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()
client = genai.Client()

MODEL = "gemini-flash-latest"


def call_gemini(prompt, retries=6, delay=15):
    for attempt in range(retries):
        try:
            return client.models.generate_content(model=MODEL, contents=prompt).text
        except errors.ServerError:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
