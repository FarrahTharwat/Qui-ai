import json
import os
import gc
import logging
from datetime import datetime
import asyncio
import fitz  # PyMuPDF
from tqdm import tqdm
import re
import torch

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Import your custom modules
from model.cleaningMultiFusion import MultiPathGrammarCorrector
from model.SimplifiedPipeline import SimplifiedPipeline
from app.services.cleaner import PDFTextCleaner
from app.services.polish import polish_text
from app.utils.extractor import PDFExtractor
from app.utils.preprocessAndClassify import analyze_all_images
from app.utils.file_handling import create_session_directories




# Initialize logger
logger = logging.getLogger(__name__)

# Environment variables
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", "")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
PAGE_THRESHOLD = int(os.getenv("PAGE_THRESHOLD", "5"))


# ---------- PDF Generation ----------
def generate_pdf_from_text(cleaned_text: str, output_dir: str) -> str:
    """Generate PDF from cleaned text with robust error handling"""
    try:
        # Validate inputs
        if not cleaned_text:
            raise ValueError("Cleaned text is empty")
        if not output_dir:
            raise ValueError("Output directory not specified")

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_pdf_path = os.path.join(output_dir, f"cleaned_{timestamp}.pdf")

        logger.info(f"Generating PDF at: {output_pdf_path}")

        # Create PDF document
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Configure styles
        styles = getSampleStyleSheet()
        styles["Title"].fontName = "Helvetica-Bold"
        styles["Title"].fontSize = 18
        styles["Title"].spaceAfter = 12
        styles["Title"].alignment = 1
        styles["Normal"].fontName = "Helvetica"
        styles["Normal"].fontSize = 12
        styles["Normal"].leading = 16
        styles["Normal"].spaceAfter = 8
        styles.add(ParagraphStyle(
            name="Metadata",
            parent=styles["Normal"],
            fontSize=10,
            spaceAfter=4
        ))

        # Build document content
        content = [
            Paragraph("Corrected Document Output", styles["Title"]),
            Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Metadata"]),
            Spacer(1, 24)
        ]

        # Add cleaned text content
        for line in cleaned_text.split("\n"):
            if line.strip():
                content.append(Paragraph(line, styles["Normal"]))

        # Build and save the document
        doc.build(content)
        logger.info(f"PDF generation completed successfully: {output_pdf_path}")
        return output_pdf_path

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise RuntimeError(f"PDF generation error: {str(e)}") from e

# Also add a fallback corrector function that can be used directly
def correct_text_simple(text, chunk_size=300):
    """Simple text correction function as backup"""
    try:
        corrector = MultiPathGrammarCorrector()
        return corrector.correct_text(text)
    except Exception as e:
        logger.error(f"Simple correction failed: {e}")
        # Return text with basic cleaning if correction fails
        return polish_text(text, correct_grammar=False)
# ---------- Grammar Correction Async ----------
async def correct_all_chunks(corrector, chunks):
    """Asynchronous grammar correction without nested thread pools"""
    results = []
    pbar = tqdm(total=len(chunks), desc="Grammar Correction")

    loop = asyncio.get_running_loop()

    # Process chunks sequentially without inner thread pool
    for chunk in chunks:
        result = await loop.run_in_executor(
            None,
            corrector.correct_chunk,
            chunk
        )
        results.append(result)
        pbar.update(1)

    pbar.close()
    return results


# ---------- Helper: Run Async in Notebook or Script ----------
def run_async_task(task):
    try:
        # Try to use existing event loop
        loop = asyncio.get_running_loop()
        future = asyncio.run_coroutine_threadsafe(task, loop)
        return future.result()
    except RuntimeError:
        # No running loop - create new one
        return asyncio.run(task)


# ---------- Image Analysis Integration ----------
def process_images_for_session(session_id: str, image_dir: str):
    """Process images and return analysis results"""
    try:
        if not os.path.exists(image_dir) or not os.listdir(image_dir):
            logger.warning(f"No images found in {image_dir}")
            return {}

        logger.info(f"Processing images in {image_dir}")
        return analyze_all_images(image_dir)
    except Exception as e:
        logger.error(f"Image processing failed: {str(e)}")
        return {}


# ---------- Main Pipeline ----------
def process_pdf_pipeline_fixed(
        pdf_path: str,
        output_dir: str,
        session_id: str,
        save_json: bool = True,
        generate_pdf_output: bool = True,
        chunk_size: int = 500,
        page_count_threshold: int = 5
) -> dict:
    """Fixed PDF processing pipeline with robust error handling"""
    try:
        # Validate inputs
        if not re.match(r"^[\w-]+$", session_id):
            raise ValueError("Invalid session ID format")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        os.makedirs(output_dir, exist_ok=True)

        # Create progress tracker
        def progress_callback(message):
            logger.info(f"Progress: {message}")
            print(f"Progress: {message}")

        logger.info(f"Starting PDF processing for: {pdf_path}")

        # Extract text
        logger.info("[1] Extracting text from PDF...")
        with fitz.open(pdf_path) as doc:
            num_pages = len(doc)

        save_images = num_pages <= page_count_threshold
        image_dir = os.path.join("static", "images", session_id)
        os.makedirs(image_dir, exist_ok=True)

        extractor = PDFExtractor(
            pdf_path=pdf_path,
            save_images=save_images,
            image_output_dir=image_dir
        )
        structured_data = extractor.extract_structured_data()

        # Process images if needed
        image_analysis = {}
        if save_images and os.path.exists(image_dir) and os.listdir(image_dir):
            logger.info("[1.5] Processing images...")
            try:
                image_analysis = process_images_for_session(session_id, image_dir)
            except Exception as e:
                logger.warning(f"Image processing failed: {e}")
                image_analysis = {}

        # Clean text
        logger.info("[2] Cleaning extracted text...")
        pages_texts = list(structured_data["pages"].values())
        page_numbers = list(structured_data["pages"].keys())

        cleaner = PDFTextCleaner()
        cleaned_pages_list = cleaner.clean_pages(pages_texts)

        # Process pages with grammar correction
        logger.info("[3] Processing pages with grammar correction...")

        # Try to initialize the pipeline, with fallback options
        pipeline = None
        try:
            pipeline = SimplifiedPipeline()
            progress_callback("Grammar correction pipeline initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize SimplifiedPipeline: {e}")
            progress_callback("Using fallback correction method")

        polished_pages = {}
        entire_polished_text = ""

        for i, page_text in enumerate(cleaned_pages_list):
            page_num = page_numbers[i]
            progress_callback(f"Processing {page_num} ({i + 1}/{len(cleaned_pages_list)})")

            if not page_text.strip():
                polished_pages[page_num] = ""
                continue

            # Basic cleaning first
            cleaned_page = cleaner.process_page(page_text)

            # Grammar correction with error handling
            try:
                if pipeline:
                    corrected_page = pipeline.process_text_chunk(
                        cleaned_page,
                        chunk_size=chunk_size,
                        progress_callback=progress_callback
                    )
                else:
                    # Fallback to simple correction
                    corrected_page = correct_text_simple(cleaned_page, chunk_size)

                # Final polishing (basic cleaning only)
                polished_page = polish_text(corrected_page, correct_grammar=False)

            except Exception as e:
                logger.error(f"Page {page_num} processing failed: {e}")
                # Use basic polish as ultimate fallback
                polished_page = polish_text(cleaned_page, correct_grammar=False)

            polished_pages[page_num] = polished_page
            entire_polished_text += polished_page + "\n\n"

            # Memory cleanup after each page
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        # Generate outputs
        output_pdf_path = None
        json_path = None

        if generate_pdf_output:
            try:
                logger.info("[4] Generating final PDF...")
                output_pdf_path = generate_pdf_from_text(entire_polished_text, output_dir)
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")
                output_pdf_path = None

        if save_json:
            try:
                json_path = os.path.join(output_dir, f"{session_id}_cleaned.json")
                logger.info(f"[5] Saving to JSON: {json_path}")

                result_data = {
                    "session_id": session_id,
                    "cleaned_text": "\n".join([cleaner.process_page(p) for p in cleaned_pages_list]),
                    "polished_text": entire_polished_text,
                    "polished_pages": polished_pages,
                    "pdf_path": output_pdf_path,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": structured_data.get("metadata", {}),
                    "image_analysis": image_analysis
                }

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"JSON saving failed: {e}")
                json_path = None

        logger.info("Pipeline completed successfully!")
        return {
            "cleaned_text": "\n".join([cleaner.process_page(p) for p in cleaned_pages_list]),
            "polished_text": entire_polished_text,
            "polished_pages": polished_pages,
            "pdf_path": output_pdf_path,
            "json_path": json_path,
            "session_id": session_id,
            "success": True
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "session_id": session_id,
            "success": False
        }
    finally:
        # Final cleanup
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()