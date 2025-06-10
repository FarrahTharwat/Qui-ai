"""# **OCR**"""
import cv2
import pytesseract
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
import re
def preprocess_image_for_ocr(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    denoised = cv2.medianBlur(thresh, 3)
    processed_pil = Image.fromarray(denoised)
    return processed_pil

def ocr_image(image_path):
    processed_image = preprocess_image_for_ocr(image_path)
    text = pytesseract.image_to_string(processed_image)
    return text

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

def choose_prompt_from_ocr(ocr_text):
    math_keywords = ['∑', '=', '∫', '\\', 'P(', 'α', 'β', '√', '∞', '≥', '≤']
    graph_keywords = ['graph', 'plot', 'axis', 'curve', 'chart', 'diagram']
    text_keywords = ['theorem', 'definition', 'proof', 'lemma', 'text']

    ocr_lower = ocr_text.lower()

    if any(k in ocr_text for k in math_keywords):
        return "a high-resolution photo of a math formula with clear symbols"
    elif any(k in ocr_lower for k in graph_keywords):
        return "a clear, colorful image of a data graph or chart"
    elif any(k in ocr_lower for k in text_keywords):
        return "a photo of a page with printed text or paragraphs"
    else:
        return "a photo of an illustration or diagram"

def caption_image_fn(image_path, prompt):
    img = Image.open(image_path).convert('RGB')
    inputs = processor(img, prompt, return_tensors="pt").to(device)
    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

def smart_caption_image(image_path, ocr_text, caption_func):
    prompt1 = choose_prompt_from_ocr(ocr_text)
    caption1 = caption_func(image_path, prompt1)

    generic_indicators = ["photo of a document", "photo of an illustration", "image"]
    if any(ind in caption1.lower() for ind in generic_indicators):
        prompt2 = "a detailed photo of a math formula or data graph"
        caption2 = caption_func(image_path, prompt2)
        caption_final = caption2 if len(caption2) > len(caption1) else caption1
    else:
        caption_final = caption1

    return caption_final

def enhanced_clean_ocr_to_latex(ocr_text):
    text = ocr_text

    replacements = {
        "∑": "\\sum",
        "∫": "\\int",
        "√": "\\sqrt",
        "∞": "\\infty",
        "≤": "\\leq",
        "≥": "\\geq",
        "≠": "\\neq",
        "→": "\\to",
        "←": "\\leftarrow",
        "α": "\\alpha",
        "β": "\\beta",
        "γ": "\\gamma",
        "Δ": "\\Delta",
        "λ": "\\lambda",
        "μ": "\\mu",
        "π": "\\pi",
        "θ": "\\theta",
        "×": "\\times",
        "÷": "\\div",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # Add LaTeX formatting for subscripts and superscripts
    text = re.sub(r'_(\w+)', r'_{\1}', text)
    text = re.sub(r'\^(\w+)', r'^{\1}', text)

    # Convert simple fractions like a/b to \frac{a}{b}
    def frac_replacer(match):
        numerator = match.group(1).strip()
        denominator = match.group(2).strip()
        return f"\\frac{{{numerator}}}{{{denominator}}}"

    text = re.sub(r'(\w+)\s*/\s*(\w+)', frac_replacer, text)

    # Remove strange characters except common LaTeX symbols
    text = re.sub(r'[^\w\s\\\^\+\-\*\/\=\{\}\(\)\[\]\.,]', '', text)

    # Normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def classify_image(ocr_text, caption):
    ocr_text = ocr_text.lower()
    caption = caption.lower()

    math_clues = ["=", "∑", "∫", "lim", "p(", "formula", "equation", "math"]
    graph_clues = ["graph", "plot", "chart", "axis", "data", "curve"]
    illustration_clues = ["diagram", "illustration", "photo", "image", "ants", "figure", "sketch"]

    if any(clue in ocr_text for clue in math_clues) or any(clue in caption for clue in math_clues):
        return "math"
    if any(clue in ocr_text for clue in graph_clues) or any(clue in caption for clue in graph_clues):
        return "graph"
    if any(clue in caption for clue in illustration_clues):
        return "illustration"
    if len(ocr_text.split()) > 20:
        return "text"
    return "unknown"

def analyze_all_images(image_dir="extracted_images"):
    results = {}
    for filename in sorted(os.listdir(image_dir)):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            path = os.path.join(image_dir, filename)

            ocr = ocr_image(path)
            prompt = choose_prompt_from_ocr(ocr)
            caption = smart_caption_image(path, ocr, caption_image_fn)
            image_type = classify_image(ocr, caption)

            latex = None
            if image_type == "math":
                latex = enhanced_clean_ocr_to_latex(ocr)

            results[filename] = {
                "ocr": ocr,
                "caption": caption,
                "prompt_used": prompt,
                "classification": image_type,
                "latex": latex,
            }
    return results


import os

def batch_process_images(image_folder, ocr_func, caption_func):
    results = {}

    for fname in sorted(os.listdir(image_folder)):
        if not fname.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        path = os.path.join(image_folder, fname)

        ocr_text = ocr_func(path)
        caption = smart_caption_image(path, ocr_text, caption_func)

        results[fname] = {
            "ocr_text": ocr_text,
            "caption": caption
        }
        print(f"Processed {fname} | OCR length: {len(ocr_text)} | Caption: {caption[:60]}...")

    return results