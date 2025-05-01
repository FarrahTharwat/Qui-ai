# app/services/cleaning_model.py
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
import tiktoken
import time
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_API_VERSION", "2024-02-01"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    max_retries=3
)


def estimate_tokens(text, model="gpt-4"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def split_text_to_chunks(text, max_tokens=2500):
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        test_chunk = f"{current_chunk}\n\n{para}".strip()
        if estimate_tokens(test_chunk) <= max_tokens:
            current_chunk = test_chunk
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def ai_clean_chunk(chunk):
    prompt = f"""STRICTLY FOLLOW THESE RULES:
1. REMOVE ALL page numbers, headers, footers, and margin text
2. FIX hyphenated words split across lines (e.g., "exam-\\nple" → "example")
3. PRESERVE original paragraph structure
4. NEVER add any new content
5. OUTPUT ONLY cleaned text

BAD EXAMPLE:
"[Chapter 1]\\nThe quick brown fox jumps over-\\nthe lazy dog. [Page 12]"

GOOD OUTPUT:
"The quick brown fox jumps over the lazy dog."

TEXT TO CLEAN:
\"\"\"{chunk}\"\"\""""

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_DEPLOYMENT"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict text cleaning engine. Follow all rules precisely."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error cleaning chunk: {str(e)}")
        return chunk  # Fallback to original text


def ai_clean_text(raw_text):
    chunks = split_text_to_chunks(raw_text)
    cleaned_chunks = []

    print(f"Processing {len(chunks)} chunks")

    for idx, chunk in enumerate(chunks):
        print(f"Cleaning chunk {idx + 1}/{len(chunks)}")
        cleaned = ai_clean_chunk(chunk)
        cleaned_chunks.append(cleaned)
        time.sleep(1.2)  # Avoid rate limits

    return "\n\n".join(cleaned_chunks)