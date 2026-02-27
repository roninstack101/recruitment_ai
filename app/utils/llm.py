import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",   # FAST + FREE
        temperature=0.3,
        api_key=os.getenv("GROQ_API_KEY")
    )

