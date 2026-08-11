import os
from google import genai
from dotenv import load_dotenv

# Carrega a tua chave do ficheiro .env
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Os modelos disponíveis na tua chave são:")
try:
    for m in client.models.list():
        print("-", m.name)
except Exception as e:
    print("Erro ao listar modelos:", e)