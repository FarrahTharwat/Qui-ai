from model.cleaningMultiFusion import MultiPathGrammarCorrector
import logging
logger = logging.getLogger(__name__)



class SimplifiedPipeline:
    """Simplified pipeline wrapper around MultiPathGrammarCorrector"""

    def __init__(self):
        self.corrector = MultiPathGrammarCorrector()
        logger.info("SimplifiedPipeline initialized with MultiPathGrammarCorrector")

    def process_text_chunk(self, text, chunk_size=500, progress_callback=None):
        """Process a text chunk with grammar correction"""
        if not text or not text.strip():
            return text

        if progress_callback:
            progress_callback(f"Processing text chunk of {len(text)} characters")

        try:
            # Split text into smaller chunks if it's too large
            if len(text) > chunk_size * 4:  # If text is very large
                sentences = text.split('. ')
                chunks = []
                current_chunk = ""

                for sentence in sentences:
                    if len(current_chunk + sentence) < chunk_size:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "

                if current_chunk:
                    chunks.append(current_chunk.strip())

                # Process each chunk
                corrected_chunks = []
                for i, chunk in enumerate(chunks):
                    if progress_callback:
                        progress_callback(f"Processing chunk {i + 1}/{len(chunks)}")
                    corrected_chunk = self.corrector.correct_text(chunk)
                    corrected_chunks.append(corrected_chunk)

                return " ".join(corrected_chunks)
            else:
                # Process as single chunk
                return self.corrector.correct_text(text)

        except Exception as e:
            logger.error(f"SimplifiedPipeline processing failed: {e}")
            if progress_callback:
                progress_callback(f"Error in processing: {e}")
            return text  # Return original text as fallback