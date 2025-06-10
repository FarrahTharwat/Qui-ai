import torch
import asyncio
import threading
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    GPT2Tokenizer,
    GPT2LMHeadModel,
    T5ForConditionalGeneration,
    BartForConditionalGeneration
)
import spacy
from spacy.cli import download
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Initialize logger
logger = logging.getLogger(__name__)


class MultiPathGrammarCorrector:
    _models_loaded = False
    _lock = threading.Lock()

    def __init__(self, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.lock = threading.Lock()
        self.batch_size = 8  # Reduced for better memory management

        # Initialize attributes
        self.nlp = None
        self.t5_tokenizer = None
        self.t5_model = None
        self.bart_tokenizer = None
        self.bart_model = None
        self.spell_tokenizer = None
        self.spell_model = None
        self.gpt2_tokenizer = None
        self.gpt2_model = None

        # Double-checked locking for model loading
        if not MultiPathGrammarCorrector._models_loaded:
            with MultiPathGrammarCorrector._lock:
                if not MultiPathGrammarCorrector._models_loaded:
                    self._load_models()
                    MultiPathGrammarCorrector._models_loaded = True
        else:
            # If model are already loaded globally, we still need to load them for this instance
            self._load_models()

    def _load_models(self):
        """Load all model only once during initialization"""
        logger.info("Loading all grammar model...")

        try:
            # Load spaCy first as it's needed for sentence segmentation
            logger.info("Loading spaCy...")
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded successfully")
            except OSError:
                logger.info("spaCy model not found, downloading...")
                try:
                    download("en_core_web_sm")
                    self.nlp = spacy.load("en_core_web_sm")
                    logger.info("spaCy model downloaded and loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to download spaCy model: {e}")
                    # Create a simple fallback tokenizer
                    self.nlp = self._create_simple_tokenizer()
                    logger.warning("Using simple fallback tokenizer")

            logger.info("Loading T5 grammar model...")
            self.t5_tokenizer = AutoTokenizer.from_pretrained("vennify/t5-base-grammar-correction")
            self.t5_model = T5ForConditionalGeneration.from_pretrained("vennify/t5-base-grammar-correction").to(
                self.device)

            logger.info("Loading BART grammar model...")
            self.bart_tokenizer = AutoTokenizer.from_pretrained("facebook/bart-base")
            self.bart_model = BartForConditionalGeneration.from_pretrained("facebook/bart-base").to(self.device)

            logger.info("Loading spelling correction model...")
            self.spell_tokenizer = AutoTokenizer.from_pretrained("oliverguhr/spelling-correction-english-base")
            self.spell_model = AutoModelForSeq2SeqLM.from_pretrained("oliverguhr/spelling-correction-english-base").to(
                self.device)

            logger.info("Loading GPT-2 for perplexity scoring...")
            self.gpt2_tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
            self.gpt2_tokenizer.pad_token = self.gpt2_tokenizer.eos_token
            self.gpt2_model = GPT2LMHeadModel.from_pretrained("gpt2").to(self.device)
            self.gpt2_model.eval()

            logger.info("All model loaded successfully!")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise RuntimeError(f"Failed to load grammar correction model: {e}")

    def _create_simple_tokenizer(self):
        """Create a simple fallback tokenizer if spaCy fails"""

        class SimpleTokenizer:
            def __call__(self, text):
                # Simple sentence splitting
                sentences = re.split(r'[.!?]+', text)
                return SimpleSentences([s.strip() for s in sentences if s.strip()])

        class SimpleSentences:
            def __init__(self, sentences):
                self.sentences = sentences

            @property
            def sents(self):
                return [SimpleSent(s) for s in self.sentences]

        class SimpleSent:
            def __init__(self, text):
                self.text = text

        return SimpleTokenizer()

    def split_into_sentences(self, text):
        """Thread-safe sentence segmentation"""
        if not text or not text.strip():
            return []

        try:
            with self.lock:  # Critical fix for thread safety
                if hasattr(self.nlp, '__call__'):
                    # Using spaCy
                    doc = self.nlp(text)
                    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
                else:
                    # Fallback to simple splitting
                    sentences = re.split(r'[.!?]+', text)
                    return [s.strip() for s in sentences if s.strip()]
        except Exception as e:
            logger.warning(f"Sentence splitting failed, using simple fallback: {e}")
            # Simple fallback
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if s.strip()]

    def correct_batch_with_model(self, sentences, model, tokenizer, prefix=""):
        """Batch correction with error handling"""
        if not sentences:
            return []

        try:
            inputs = [prefix + s for s in sentences]
            encodings = tokenizer(
                inputs,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128
            ).to(self.device)

            outputs = model.generate(
                **encodings,
                max_length=128,
                num_beams=5,
                early_stopping=True
            )

            decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)

            # Remove prefix if present
            if prefix:
                decoded = [d[len(prefix):] if d.startswith(prefix) else d for d in decoded]

            # Clean up artifacts in batch
            cleaned = []
            for d in decoded:
                d = re.sub(r'^(Corrected|Correcting|Correct|Fixed|Fixing|Fix)[:,\s]*', '', d, flags=re.IGNORECASE)
                d = d.strip()
                if d:
                    d = d[0].upper() + d[1:]
                cleaned.append(d)

            return cleaned

        except Exception as e:
            logger.error(f"Batch correction failed: {str(e)}")
            return sentences

    def score_perplexity_batch(self, sentences):
        """Fixed batch perplexity calculation"""
        if not sentences:
            return [float('inf')] * len(sentences)

        try:
            encodings = self.gpt2_tokenizer(
                sentences,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128
            ).to(self.device)

            input_ids = encodings.input_ids
            attention_mask = encodings.attention_mask

            with torch.no_grad():
                outputs = self.gpt2_model(input_ids, attention_mask=attention_mask)
                logits = outputs.logits

            # Calculate perplexity per sentence
            perplexities = []
            loss_fct = torch.nn.CrossEntropyLoss(reduction='none')

            for i in range(input_ids.size(0)):
                shift_logits = logits[i, :-1, :].contiguous()
                shift_labels = input_ids[i, 1:].contiguous()

                # Compute loss
                loss = loss_fct(
                    shift_logits.view(-1, shift_logits.size(-1)),
                    shift_labels.view(-1)
                )

                # Mask loss for padding
                mask = (shift_labels != self.gpt2_tokenizer.pad_token_id).float()
                if mask.sum() > 0:
                    nll = (loss * mask).sum() / mask.sum()
                    perplexities.append(torch.exp(nll).item())
                else:
                    perplexities.append(float('inf'))

            return perplexities

        except Exception as e:
            logger.error(f"Batch perplexity scoring failed: {str(e)}")
            return [float('inf')] * len(sentences)

    def fusion_choose_best_batch(self, t5_out, bart_out, spell_out):
        """Optimized batch fusion using parallel perplexity scoring"""
        if not t5_out or len(t5_out) == 0:
            return []

        try:
            # Flatten all candidates for batch scoring
            all_candidates = []
            for i in range(len(t5_out)):
                all_candidates.extend([
                    t5_out[i] if i < len(t5_out) else "",
                    bart_out[i] if i < len(bart_out) else "",
                    spell_out[i] if i < len(spell_out) else ""
                ])

            # Score all candidates in a single batch
            perplexities = self.score_perplexity_batch(all_candidates)

            # Reconstruct results with batch processing
            fused = []
            for i in range(len(t5_out)):
                base_idx = i * 3
                if base_idx + 2 < len(perplexities):
                    scores = {
                        "t5": perplexities[base_idx],
                        "bart": perplexities[base_idx + 1],
                        "spell": perplexities[base_idx + 2]
                    }
                    best = min(scores, key=scores.get)

                    # Select the best candidate
                    candidates = {
                        "t5": t5_out[i] if i < len(t5_out) else "",
                        "bart": bart_out[i] if i < len(bart_out) else "",
                        "spell": spell_out[i] if i < len(spell_out) else ""
                    }
                    fused.append(candidates[best])
                else:
                    # Fallback to first available option
                    fused.append(t5_out[i] if i < len(t5_out) else "")

            return fused
        except Exception as e:
            logger.error(f"Fusion failed: {e}")
            return t5_out  # Return T5 results as fallback

    def correct_text(self, text):
        """Memory-optimized text correction with batch fusion"""
        if not text or not text.strip():
            return text

        try:
            sentences = self.split_into_sentences(text)
            if not sentences:
                return text

            logger.info(f"Correcting {len(sentences)} sentences in batches of {self.batch_size}")

            t5_out, bart_out, spell_out = [], [], []

            # Process in batches with memory management
            for i in range(0, len(sentences), self.batch_size):
                batch = sentences[i:i + self.batch_size]
                logger.debug(
                    f"Processing batch {i // self.batch_size + 1}/{(len(sentences) + self.batch_size - 1) // self.batch_size}")

                # Parallel model processing
                with ThreadPoolExecutor(max_workers=3) as executor:
                    t5_future = executor.submit(
                        self.correct_batch_with_model,
                        batch, self.t5_model, self.t5_tokenizer, "grammar: "
                    )
                    bart_future = executor.submit(
                        self.correct_batch_with_model,
                        batch, self.bart_model, self.bart_tokenizer, ""
                    )
                    spell_future = executor.submit(
                        self.correct_batch_with_model,
                        batch, self.spell_model, self.spell_tokenizer, "correct: "
                    )

                    t5_batch = t5_future.result()
                    bart_batch = bart_future.result()
                    spell_batch = spell_future.result()

                t5_out.extend(t5_batch)
                bart_out.extend(bart_batch)
                spell_out.extend(spell_batch)

                # Memory cleanup
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # Final fusion
            fused_results = self.fusion_choose_best_batch(t5_out, bart_out, spell_out)
            return " ".join(fused_results)

        except Exception as e:
            logger.error(f"Text correction failed: {e}")
            return text  # Return original text as fallback

    def correct_chunk(self, text_chunk):
        """Process a single chunk of text"""
        return self.correct_text(text_chunk)