import os
import json
import re
import time
import streamlit as st
from google import genai

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")

def get_client():
    return genai.Client(api_key=get_api_key())

def generate_word_question(exclude_words: list = []) -> dict:
    exclude_str = ", ".join(exclude_words[-20:]) if exclude_words else "none"
    prompt = f"""
You are an English vocabulary teacher for Thai learners.
Generate a B1-B2 level English vocabulary question.
Do NOT use these recently seen words: {exclude_str}

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "word": "the target word",
  "word_th": "คำแปลภาษาไทย",
  "sentence": "A natural example sentence using the word",
  "sentence_th": "คำแปลประโยคเป็นภาษาไทย",
  "blank_sentence": "The same sentence but replace the target word with _____",
  "options": [
    {{"word": "correct word", "word_th": "คำแปล", "is_correct": true}},
    {{"word": "wrong word 1", "word_th": "คำแปล", "is_correct": false}},
    {{"word": "wrong word 2", "word_th": "คำแปล", "is_correct": false}},
    {{"word": "wrong word 3", "word_th": "คำแปล", "is_correct": false}}
  ]
}}
"""
    client = get_client()
    time.sleep(1)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)

def generate_review_question(word: str, word_th: str) -> dict:
    prompt = f"""
You are an English vocabulary teacher for Thai learners.
Generate a review question for this word: "{word}" (ความหมาย: {word_th})

Return ONLY valid JSON in this exact format:
{{
  "word": "{word}",
  "word_th": "{word_th}",
  "sentence": "A NEW example sentence using {word}",
  "sentence_th": "คำแปลประโยคเป็นภาษาไทย",
  "blank_sentence": "The same sentence but replace {word} with _____",
  "options": [
    {{"word": "correct word", "word_th": "คำแปล", "is_correct": true}},
    {{"word": "wrong word 1", "word_th": "คำแปล", "is_correct": false}},
    {{"word": "wrong word 2", "word_th": "คำแปล", "is_correct": false}},
    {{"word": "wrong word 3", "word_th": "คำแปล", "is_correct": false}}
  ]
}}
"""
    client = get_client()
    time.sleep(1)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)
