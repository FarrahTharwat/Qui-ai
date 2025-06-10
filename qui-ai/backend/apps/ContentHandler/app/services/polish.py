""# **POLISHING**"""
import hashlib
from tqdm import tqdm
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import re
# In-memory cache
_polish_cache = {}

def _cache_key(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_model(model_name="pszemraj/flan-t5-large-grammar-synthesis"):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return tokenizer, model

def polish_text(text: str, correct_grammar=True, model=None, tokenizer=None, batch_size=512):
    """
    Polishes and optionally corrects text using regex + grammar correction model.

    Args:
        text (str): Raw input text to polish.
        correct_grammar (bool): Whether to correct using pretrained model.
        model, tokenizer: Preloaded Hugging Face model and tokenizer (if used in batch).
        batch_size (int): Max tokens per batch for correction.

    Returns:
        str: Polished text.
    """

    # 1. Hyphenated line breaks
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # 2. Merge broken lines
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

    # 3. Collapse excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 4. Normalize punctuation
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.replace("–", "-").replace("—", "-")

    # 5. Remove extra spaces
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    text = text.strip()

    if not correct_grammar:
        return text

    # 6. Grammar Correction (Batching + Caching)
    try:
        if not model or not tokenizer:
            tokenizer, model = load_model()

        sentences = re.split(r'(?<=[.?!])\s+', text)  # basic sentence split
        polished_sentences = []

        for sentence in tqdm(sentences, desc="Polishing grammar"):
            key = _cache_key(sentence)
            if key in _polish_cache:
                polished_sentences.append(_polish_cache[key])
                continue

            inputs = tokenizer(sentence, return_tensors="pt", truncation=True, max_length=batch_size)
            output = model.generate(**inputs, max_new_tokens=batch_size)
            cleaned = tokenizer.decode(output[0], skip_special_tokens=True)

            _polish_cache[key] = cleaned
            polished_sentences.append(cleaned)

        return " ".join(polished_sentences)

    except Exception as e:
        print(f"[Warning] Skipped grammar polishing: {e}")
        return text


