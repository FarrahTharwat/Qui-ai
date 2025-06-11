# app/core/mcq_generator.py
"""
Core MCQ Generator Module - Modified for Supabase Integration
T5 for Question Generation + RoBERTa for Answer Extraction
Works with cleaned text from database instead of PDF files
"""

import nltk
import random
import re
import logging
from keybert import KeyBERT
from transformers import (
    T5Tokenizer, T5ForConditionalGeneration,
    AutoTokenizer, AutoModelForSequenceClassification,
    pipeline
)
from sentence_transformers import SentenceTransformer, util
import torch
import unicodedata

logger = logging.getLogger(__name__)

# Global variables for models
_models_loaded = False
_kw_model = None
_qg_tokenizer = None
_qg_model = None
_sbert_model = None
_qa_pipeline = None
_cola_tokenizer = None
_cola_model = None
_stop_words = None

def load_models():
    """Load all models once at startup"""
    global _models_loaded, _kw_model, _qg_tokenizer, _qg_model, _sbert_model
    global _qa_pipeline, _cola_tokenizer, _cola_model, _stop_words
    
    if _models_loaded:
        return
    
    try:
        logger.info("Loading MCQ generation models...")
        
        # Download NLTK data
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('punkt_tab', quiet=True)
            nltk.download('averaged_perceptron_tagger', quiet=True)
            nltk.download('averaged_perceptron_tagger_eng', quiet=True)
            nltk.download('stopwords', quiet=True)
        except Exception as e:
            logger.warning(f"NLTK download warning: {e}")
        
        from nltk.corpus import stopwords
        _stop_words = set(stopwords.words('english'))
        
        # Load models
        _kw_model = KeyBERT('all-MiniLM-L6-v2')
        _qg_tokenizer = T5Tokenizer.from_pretrained("valhalla/t5-base-qg-hl")
        _qg_model = T5ForConditionalGeneration.from_pretrained("valhalla/t5-base-qg-hl")
        _sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # RoBERTa QA Pipeline
        _qa_pipeline = pipeline(
            "question-answering", 
            model="deepset/roberta-base-squad2", 
            tokenizer="deepset/roberta-base-squad2"
        )
        
        # BERT-CoLA model
        _cola_tokenizer = AutoTokenizer.from_pretrained("textattack/bert-base-uncased-CoLA")
        _cola_model = AutoModelForSequenceClassification.from_pretrained("textattack/bert-base-uncased-CoLA")
        _cola_model.eval()
        
        _models_loaded = True
        logger.info("All MCQ models loaded successfully!")
        
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        raise

def split_into_chunks(text, min_words=30, max_words=100):
    """Create meaningful chunks based on sentence boundaries"""
    if not text.strip():
        return []

    try:
        from nltk import sent_tokenize
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = []
        current_words = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())

            if current_words + sentence_words > max_words and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if current_words >= min_words:
                    chunks.append(chunk_text)
                current_chunk = [sentence]
                current_words = sentence_words
            else:
                current_chunk.append(sentence)
                current_words += sentence_words

        if current_chunk and current_words >= min_words:
            chunks.append(' '.join(current_chunk))

        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        return []

def extract_quality_keyphrases(chunk, top_n=5):
    """Extract meaningful keyphrases with validation"""
    load_models()  # Ensure models are loaded
    
    try:
        if len(chunk.split()) < 10:
            return []

        keyphrases = _kw_model.extract_keywords(
            chunk,
            keyphrase_ngram_range=(1, 3),
            stop_words='english',
            top_n=top_n * 2,
            diversity=0.7
        )

        valid_phrases = []
        for phrase, score in keyphrases:
            if is_valid_keyphrase(phrase, score):
                valid_phrases.append(phrase)

        return valid_phrases[:top_n]
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        return []

def is_valid_keyphrase(phrase, score):
    """Validate if a keyphrase is suitable for MCQ"""
    if score < 0.4 or len(phrase) < 3 or len(phrase) > 50:
        return False
    
    if phrase.isdigit() or (len(phrase.split()) == 1 and len(phrase) <= 2):
        return False
    
    if phrase.lower() in _stop_words:
        return False
    
    if not any(c.isalpha() for c in phrase):
        return False
    
    generic_terms = ['system', 'process', 'method', 'approach', 'technique', 'way', 'thing']
    if phrase.lower() in generic_terms:
        return False

    return True

def generate_quality_question(context, target_keyphrase):
    """Generate well-formed questions targeting a keyphrase using T5"""
    load_models()
    
    try:
        context = clean_text_for_generation(context)
        target_keyphrase = clean_text_for_generation(target_keyphrase)

        if len(context.split()) > 100:
            context = ' '.join(context.split()[:100])

        highlighted_context = context.replace(target_keyphrase, f"<hl> {target_keyphrase} <hl>")
        input_text = f"generate question: {highlighted_context}"

        inputs = _qg_tokenizer.encode(
            input_text,
            return_tensors="pt",
            max_length=512,
            truncation=True
        )

        outputs = _qg_model.generate(
            inputs,
            max_length=64,
            num_beams=3,
            early_stopping=True,
            do_sample=False,
            repetition_penalty=1.2
        )

        question = _qg_tokenizer.decode(outputs[0], skip_special_tokens=True)
        question = post_process_question(question, target_keyphrase)

        return question if is_valid_question(question, target_keyphrase) else None

    except Exception as e:
        logger.error(f"Error generating question: {e}")
        return None

def clean_text_for_generation(text):
    """Clean text for better generation"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,;:!?()-]', '', text)
    return text.strip()

def post_process_question(question, target_keyphrase):
    """Clean up generated questions"""
    question = question.strip()
    question = re.sub(r'\s+', ' ', question)
    question = re.sub(r'^(what|who|when|where|why|how)\s+',
                     lambda m: m.group(0).capitalize(), question, flags=re.IGNORECASE)

    if not question.endswith('?'):
        question += '?'

    words = question.split()
    cleaned_words = []
    for word in words:
        if not cleaned_words or word.lower() != cleaned_words[-1].lower():
            cleaned_words.append(word)

    return ' '.join(cleaned_words)

def is_valid_question(question, target_keyphrase):
    """Validate question quality"""
    if not question or len(question) < 10 or not question.endswith('?'):
        return False

    question_starters = ['what', 'who', 'when', 'where', 'why', 'how', 'which', 'does', 'do', 'is', 'are', 'can', 'will']
    if not any(question.lower().startswith(starter) for starter in question_starters):
        return False

    if target_keyphrase.lower() in question.lower():
        return False

    return True

def extract_answer_with_roberta(question, context):
    """Use RoBERTa to extract the correct answer from context"""
    load_models()
    
    try:
        if len(context.split()) > 400:
            context = ' '.join(context.split()[:400])
        
        result = _qa_pipeline(question=question, context=context)
        
        answer = result['answer'].strip()
        confidence = result['score']
        
        if confidence < 0.1:
            return None, 0
        
        if is_valid_roberta_answer(answer, question, context):
            return answer, confidence
        else:
            return None, 0
            
    except Exception as e:
        logger.error(f"Error extracting answer with RoBERTa: {e}")
        return None, 0

def is_valid_roberta_answer(answer, question, context):
    """Validate if RoBERTa's answer is suitable for MCQ"""
    if not answer or len(answer.strip()) < 2:
        return False
    
    if len(answer.split()) > 8:
        return False
    
    if answer.lower() not in context.lower():
        return False
    
    if not any(c.isalpha() for c in answer):
        return False
    
    question_words = set(question.lower().split())
    answer_words = set(answer.lower().split())
    if len(question_words & answer_words) > len(answer_words) * 0.5:
        return False
    
    return True

def generate_quality_distractors(correct_answer, context, all_keyphrases, num_distractors=3):
    """Generate contextually relevant distractors"""
    try:
        distractors = set()

        # Use other keyphrases from context
        context_phrases = [kp for kp in all_keyphrases
                          if kp.lower() != correct_answer.lower() and
                          similar_length(kp, correct_answer)]
        distractors.update(context_phrases[:2])

        # Extract noun phrases from context
        noun_phrases = extract_noun_phrases(context)
        relevant_phrases = [np for np in noun_phrases
                           if np.lower() != correct_answer.lower() and
                           similar_length(np, correct_answer) and
                           is_valid_distractor(np, correct_answer)]
        distractors.update(relevant_phrases[:2])

        # Semantic similarity
        if len(distractors) < num_distractors:
            semantic_distractors = get_semantic_distractors(correct_answer, context)
            distractors.update(semantic_distractors)

        final_distractors = list(distractors)[:num_distractors]

        if len(final_distractors) < 2:
            return None

        return final_distractors

    except Exception as e:
        logger.error(f"Error generating distractors: {e}")
        return None

def extract_noun_phrases(text):
    """Extract noun phrases from text"""
    try:
        from nltk import word_tokenize, pos_tag
        tokens = word_tokenize(text)
        pos_tags = pos_tag(tokens)

        noun_phrases = []
        current_phrase = []

        for word, pos in pos_tags:
            if pos.startswith('NN') or pos.startswith('JJ'):
                current_phrase.append(word)
            else:
                if current_phrase and len(current_phrase) <= 3:
                    phrase = ' '.join(current_phrase)
                    if is_valid_keyphrase(phrase, 0.5):
                        noun_phrases.append(phrase)
                current_phrase = []

        if current_phrase and len(current_phrase) <= 3:
            phrase = ' '.join(current_phrase)
            if is_valid_keyphrase(phrase, 0.5):
                noun_phrases.append(phrase)

        return list(set(noun_phrases))[:10]
    except:
        return []

def similar_length(str1, str2, tolerance=0.5):
    """Check if two strings have similar length"""
    len1, len2 = len(str1.split()), len(str2.split())
    if len1 == 0 or len2 == 0:
        return False
    ratio = min(len1, len2) / max(len1, len2)
    return ratio >= tolerance

def is_valid_distractor(distractor, answer):
    """Check if distractor is valid"""
    if distractor.lower() == answer.lower():
        return False
    if distractor.lower() in answer.lower() or answer.lower() in distractor.lower():
        return False
    return True

def get_semantic_distractors(answer, context):
    """Get semantically similar but distinct distractors"""
    load_models()
    
    try:
        words = [w for w in context.split()
                if w.isalpha() and len(w) > 3 and
                w.lower() not in _stop_words and
                w.lower() != answer.lower()]

        if len(words) < 3:
            return []

        answer_emb = _sbert_model.encode(answer, convert_to_tensor=True)
        word_embs = _sbert_model.encode(words, convert_to_tensor=True)
        similarities = util.pytorch_cos_sim(answer_emb, word_embs)[0]

        valid_indices = []
        for i, sim in enumerate(similarities):
            if 0.3 < sim < 0.8:
                valid_indices.append(i)

        if valid_indices:
            selected_indices = valid_indices[:3]
            return [words[i] for i in selected_indices]

        return []
    except:
        return []

def is_grammatically_correct(sentence, threshold=0.85):
    """Use BERT CoLA to evaluate grammatical acceptability"""
    load_models()
    
    try:
        inputs = _cola_tokenizer(sentence, return_tensors="pt", truncation=True)
        with torch.no_grad():
            outputs = _cola_model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)
            accept_prob = probs[0][1].item()

        return accept_prob >= threshold
    except:
        return True

def create_quality_mcq(question, correct_answer, distractors, context, confidence):
    """Create MCQ with quality validation"""
    if not all([question, correct_answer, distractors]) or len(distractors) < 2:
        return None

    options = [opt.strip() for opt in distractors + [correct_answer] if opt.strip()]
    options = list(set(options))

    if len(options) < 3:
        return None

    lengths = [len(opt.split()) for opt in options]
    if max(lengths) - min(lengths) > 5:
        return None

    random.shuffle(options)
    correct_letter = chr(65 + options.index(correct_answer))

    return {
        "question": question,
        "options": options[:4],
        "answer": correct_letter,
        "correct_answer": correct_answer,
        "confidence": round(confidence, 3),
        "context": context[:200] + "..." if len(context) > 200 else context,
        "difficulty": assess_difficulty(question, correct_answer, distractors, confidence)
    }

def assess_difficulty(question, answer, distractors, confidence):
    """Assess MCQ difficulty level"""
    q_complexity = len(question.split())
    a_complexity = len(answer.split())
    d_similarity = sum(1 for d in distractors if any(word in d.lower().split() for word in answer.lower().split()))

    confidence_factor = 0 if confidence > 0.8 else (1 if confidence > 0.5 else 2)

    difficulty_score = 0
    if q_complexity > 15 or a_complexity > 3 or d_similarity > 1:
        difficulty_score += 2
    elif q_complexity > 10 or a_complexity > 2:
        difficulty_score += 1
    
    difficulty_score += confidence_factor

    if difficulty_score >= 3:
        return "Hard"
    elif difficulty_score >= 1:
        return "Medium"
    else:
        return "Easy"

def generate_quality_mcqs_from_text(text):
    """
    Generate high-quality MCQs from cleaned text (no limits on chunks or MCQs)
    
    Args:
        text: The cleaned text from the database
        
    Returns:
        List of MCQ dictionaries
    """
    load_models()  # Ensure models are loaded
    
    logger.info("Processing text for MCQ generation...")

    if not text or not text.strip():
        logger.warning("No text provided!")
        return []

    logger.info("Creating chunks from text...")
    chunks = split_into_chunks(text)
    logger.info(f"Created {len(chunks)} chunks")

    if not chunks:
        logger.warning("No valid chunks created!")
        return []

    # Collect all keyphrases first
    logger.info("Extracting keyphrases from all chunks...")
    all_keyphrases = []
    chunk_keyphrases = {}

    for i, chunk in enumerate(chunks):
        keyphrases = extract_quality_keyphrases(chunk)
        chunk_keyphrases[i] = keyphrases
        all_keyphrases.extend(keyphrases)

    logger.info(f"Extracted {len(all_keyphrases)} total keyphrases")

    # Generate MCQs from all chunks
    logger.info("Generating MCQs with T5 + RoBERTa...")
    mcqs = []
    seen_questions = set()

    for i, chunk in enumerate(chunks):
        keyphrases = chunk_keyphrases.get(i, [])
        if not keyphrases:
            continue

        logger.info(f"Processing chunk {i+1}/{len(chunks)} with {len(keyphrases)} keyphrases")

        for target_keyphrase in keyphrases:
            try:
                question = generate_quality_question(chunk, target_keyphrase)

                if not question or question in seen_questions:
                    continue
                    
                if not is_grammatically_correct(question):
                    logger.debug(f"Skipped grammatically weak question: {question}")
                    continue

                roberta_answer, confidence = extract_answer_with_roberta(question, chunk)
                
                if not roberta_answer or confidence < 0.15:
                    continue

                distractors = generate_quality_distractors(roberta_answer, chunk, all_keyphrases)
                if not distractors:
                    continue

                mcq = create_quality_mcq(question, roberta_answer, distractors, chunk, confidence)
                if mcq:
                    mcqs.append(mcq)
                    seen_questions.add(question)
                    logger.debug(f"Generated MCQ {len(mcqs)}: {question[:50]}...")

            except Exception as e:
                logger.error(f"Error generating MCQ from keyphrase '{target_keyphrase}': {e}")
                continue

    logger.info(f"Generated {len(mcqs)} quality MCQs from text!")
    return mcqs

def display_mcqs_enhanced(mcqs):
    """Display MCQs with enhanced formatting"""
    if not mcqs:
        print("No MCQs generated!")
        return

    print(f"\n{'='*60}")
    print(f"GENERATED {len(mcqs)} HIGH-QUALITY MCQs (T5 + RoBERTa)")
    print(f"{'='*60}")

    difficulties = [mcq['difficulty'] for mcq in mcqs]
    confidences = [mcq['confidence'] for mcq in mcqs]
    
    print(f"\nSTATISTICS:")
    print(f"Easy: {difficulties.count('Easy')} | Medium: {difficulties.count('Medium')} | Hard: {difficulties.count('Hard')}")
    print(f"Average RoBERTa Confidence: {sum(confidences)/len(confidences):.3f}")

    for i, mcq in enumerate(mcqs, 1):
        print(f"\nQ{i}: {mcq['question']}")
        print(f"Difficulty: {mcq['difficulty']} | Confidence: {mcq['confidence']}")
        print("-" * 40)

        for idx, opt in enumerate(mcq['options']):
            marker = "✓" if chr(65+idx) == mcq['answer'] else " "
            print(f"  {chr(65+idx)}) {opt} {marker}")

        print(f"\nCorrect Answer: {mcq['answer']} ({mcq['correct_answer']})")
        print(f"Context: {mcq['context']}")
        print("=" * 60)