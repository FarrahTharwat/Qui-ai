import os
import re
import time
import tiktoken
from typing import List, Tuple
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT")
)

# --- Utility functions ---

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text)) + 100

def intelligent_chunking(text: str, max_tokens: int = 1800) -> List[Tuple[int, int, str]]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current_chunk, current_tokens = [], [], 0
    start_index = 0

    for sentence in sentences:
        tokens = estimate_tokens(sentence)
        if current_tokens + tokens > max_tokens:
            chunk_text = ' '.join(current_chunk)
            chunks.append((start_index, start_index + len(chunk_text), chunk_text))
            start_index += len(chunk_text) + 1
            current_chunk, current_tokens = [sentence], tokens
        else:
            current_chunk.append(sentence)
            current_tokens += tokens

    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append((start_index, start_index + len(chunk_text), chunk_text))

    return chunks

# --- Main model call ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def ai_clean_chunk(chunk: str, chunk_num: int, total_chunks: int) -> str:
    prompt = f"""You are a strict and accurate text cleaning assistant.

INSTRUCTIONS:
- Remove page numbers (e.g. "Page 12", "pg. 5"), metadata (ISBN, DOI, license).
- Remove repeated headers and footers.
- Fix broken words across lines (e.g. "arti-\nficial" → "artificial").
- Merge lines inside a paragraph but preserve paragraph breaks.
- Do NOT change technical content or formatting.
- Never paraphrase. Never add new text.

CLEAN THIS (chunk {chunk_num}/{total_chunks}):
\"\"\"{chunk}\"\"\""""

    response = client.chat.completions.create(
        model=os.getenv("AZURE_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": "You are a careful, rule-based book cleaner."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()

# --- Full cleaning pipeline ---

def ai_clean_text(raw_text: str) -> str:
    # Initial cleanup
    raw_text = re.sub(r'\b(?:Page|pg|Pg|P)\.?\s*\d+\b', '', raw_text)
    raw_text = re.sub(r'(ISBN|DOI|©|Library of Congress|Springer).*\n?', '', raw_text)
    raw_text = re.sub(r'\n{3,}', '\n\n', raw_text)

    chunks = intelligent_chunking(raw_text)
    print(f"🔍 Processing {len(chunks)} chunks...")

    cleaned_chunks = []
    for idx, (_, _, chunk) in enumerate(chunks):
        print(f"🧼 Cleaning chunk {idx+1}/{len(chunks)}...")
        cleaned_chunk = ai_clean_chunk(chunk, idx+1, len(chunks))
        cleaned_chunks.append(cleaned_chunk)
        time.sleep(1.5)  # Rate limit buffer

    final_text = "\n\n".join(cleaned_chunks)

    # Final polish
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    final_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', final_text)

    return final_text
