import os
import json
import re
import google.generativeai as genai

def get_client():
    import streamlit as st
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")

def generate_word_question(exclude_words: list[str] = []) -> dict:
    """
    Generate a B1-B2 English word with Thai translation,
    example sentence, and 4 multiple-choice options.
    Returns dict with keys: word, word_th, sentence, sentence_th,
    blank_sentence, options (list of {word, word_th, is_correct})
    """
    exclude_str = ", ".join(exclude_words[-20:]) if exclude_words else "none"

    prompt = f"""
You are an English vocabulary teacher for Thai learners.
Generate a B1-B2 level English vocabulary question.
Do NOT use these recently seen words: {exclude_str}

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "word": "the target word",
  "word_th": "คำแปลภาษาไทย",
  "sentence": "A natural example sentence using the word, with the word present",
  "sentence_th": "คำแปลประโยคเป็นภาษาไทย",
  "blank_sentence": "The same sentence but replace the target word with _____",
  "options": [
    {{"word": "correct word", "word_th": "คำแปล", "is_correct": true}},
    {{"word": "wrong word 1", "word_th": "คำแปล", "is_correct": false}},
    {{"word": "wrong word 2", "word_th": "คำแปล", "is_correct": false}},
    {{"word": "wrong word 3", "word_th": "คำแปล", "is_correct": false}}
  ]
}}

Rules:
- The 4 options must all be plausible English words (B1-C1 level)
- Wrong options should be similar in meaning or usage to make it challenging
- Shuffle the options so correct answer is not always first
- Sentence should be natural and contextual (daily life, work, travel, feelings)
- Thai translations should be clear and natural
"""

    model = get_client()
    response = model.generate_content(prompt)
    text = response.text.strip()

    # Strip markdown code fences if present
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    data = json.loads(text)
    return data


def generate_review_question(word: str, word_th: str) -> dict:
    """Generate a review question for a specific word the user previously got wrong."""
    prompt = f"""
You are an English vocabulary teacher for Thai learners.
Generate a review question for this specific word: "{word}" (ความหมาย: {word_th})

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "word": "{word}",
  "word_th": "{word_th}",
  "sentence": "A NEW example sentence using the word (different context from before)",
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
    model = get_client()
    response = model.generate_content(prompt)
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    return data
