# app/services/cleaning_model.py
from openai import AzureOpenAI
import os
import re
import tiktoken
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from typing import List, Tuple

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_API_VERSION", "2024-02-01"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    max_retries=5
)


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """More accurate token estimation with safety margin"""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text)) + 100  # Add buffer for prompt


def intelligent_chunking(text: str, max_tokens: int = 1800) -> List[Tuple[int, int, str]]:
    """
    Split text into chunks with context-aware boundaries
    Returns list of (start_idx, end_idx, chunk) tuples
    """
    chunks = []
    current_start = 0
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s+', text)

    current_chunk = []
    current_token_count = 0

    for sentence in sentences:
        sentence_token_count = estimate_tokens(sentence)

        if current_token_count + sentence_token_count > max_tokens:
            # Save current chunk
            chunk_text = ' '.join(current_chunk)
            chunks.append((
                current_start,
                current_start + len(chunk_text),
                chunk_text
            ))

            # Reset
            current_start += len(chunk_text) + 1
            current_chunk = [sentence]
            current_token_count = sentence_token_count
        else:
            current_chunk.append(sentence)
            current_token_count += sentence_token_count

    # Add remaining text
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append((
            current_start,
            current_start + len(chunk_text),
            chunk_text
        ))

    return chunks


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def ai_clean_chunk(chunk: str, chunk_num: int, total_chunks: int) -> str:
    """Enhanced cleaning with position-aware context"""
    prompt = f"""CLEANING RULES (STRICT):
1. REMOVE ALL:
   - Page numbers (e.g., "Page 3", "P.12")
   - Headers/footers (e.g., "CHAPTER 1", "CONFIDENTIAL")
   - Margin notes, watermarks
   - ISBN/DOI numbers
2. FIX:
   - Hyphenated line breaks → "exam-\\nple" → "example"
   - Misplaced line breaks between sentences
3. PRESERVE:
   - Paragraph structure
   - Original punctuation
   - Technical terms/names
4. NEVER:
   - Add/remove content
   - Paraphrase
   - Change formatting

BAD INPUT:
"[Page 5]\\nThe quick brown fox jumps over-\\nthe lazy dog. [DOI:10.1234]"

GOOD OUTPUT:
"The quick brown fox jumps over the lazy dog."

CURRENT CHUNK ({chunk_num}/{total_chunks}):
\"\"\"{chunk}\"\"\""""

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_DEPLOYMENT"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a forensic text cleaner. Apply rules exactly. Never invent content."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # More deterministic
            top_p=0.3,
            max_tokens=2000
        )
        cleaned = response.choices[0].message.content.strip()

        # Validation heuristics
        if len(cleaned) < 0.5 * len(chunk):
            raise ValueError("Excessive content removal detected")

        return cleaned

    except Exception as e:
        print(f"Error cleaning chunk {chunk_num}: {str(e)}")
        return chunk  # Fallback with original content


def ai_clean_text(raw_text: str) -> str:
    """Full cleaning pipeline with validation"""
    # Pre-clean obvious patterns
    raw_text = re.sub(r'\nPage \d+\n', '\n', raw_text)
    raw_text = re.sub(r'\b(?:Page|P|pg)\.?\s*\d+\b', '', raw_text)

    chunks = intelligent_chunking(raw_text)
    cleaned_chunks = []

    print(f"Processing {len(chunks)} text chunks")

    for idx, (start, end, chunk) in enumerate(chunks):
        print(f"Cleaning chunk {idx + 1}/{len(chunks)} ({end - start} chars)")
        cleaned = ai_clean_chunk(chunk, idx + 1, len(chunks))
        cleaned_chunks.append(cleaned)
        time.sleep(1.5)  # Rate limit buffer

    # Post-processing
    final_text = '\n'.join(cleaned_chunks)

    # Remove residual artifacts
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)  # Reduce excessive newlines
    final_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', final_text)  # Fix single newlines

    return final_text


def generate_diff(raw: str, cleaned: str) -> str:
    """Create HTML diff for visual comparison"""
    from difflib import HtmlDiff
    differ = HtmlDiff()
    return differ.make_file(
        raw.splitlines(),
        cleaned.splitlines(),
        context=True,
        numlines=2
    )