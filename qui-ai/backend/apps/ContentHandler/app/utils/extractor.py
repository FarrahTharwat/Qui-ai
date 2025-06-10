import os
import ftfy
import fitz  # PyMuPDF
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

import fitz  # PyMuPDF

class PDFExtractor:
    def __init__(self, pdf_path, save_images=False, image_output_dir="extracted_images"):
        self.pdf_path = pdf_path
        self.save_images = save_images
        self.image_output_dir = image_output_dir
        if save_images:
            os.makedirs(image_output_dir, exist_ok=True)
            logger.info(f"Image output directory: {image_output_dir}")

    def extract_structured_data(self):
        """Returns dictionary with metadata and page contents"""
        doc = fitz.open(self.pdf_path)
        metadata = doc.metadata
        metadata["page_count"] = len(doc)

        pages = {}
        for i in range(len(doc)):
            page = doc[i]
            try:
                # Extract text with formatting preserved
                text = page.get_text("text", sort=True)
                fixed_text = ftfy.fix_text(text) if text else ""
                pages[f"page_{i + 1}"] = fixed_text

                # Extract images if enabled
                if self.save_images:
                    self._extract_images_from_page(page, i)
            except Exception as e:
                logger.error(f"Error processing page {i + 1}: {e}")
                pages[f"page_{i + 1}"] = f"Error processing page: {str(e)}"

        doc.close()
        return {
            "metadata": metadata,
            "pages": pages
        }

    def _extract_images_from_page(self, page, page_index):
        """Extract images from a PDF page using PyMuPDF"""
        try:
            image_list = page.get_images(full=True)
            if not image_list:
                logger.debug(f"No images found on page {page_index + 1}")
                return

            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = None
                try:
                    base_image = page.parent.extract_image(xref)
                    image_data = base_image["image"]

                    # Get image format
                    ext = base_image.get("ext", "png")
                    if ext.lower() not in ["jpg", "jpeg", "png", "gif", "bmp"]:
                        ext = "png"

                    # Save image to file
                    image_path = os.path.join(
                        self.image_output_dir,
                        f"page_{page_index + 1}_img_{img_index + 1}.{ext}"
                    )

                    with open(image_path, "wb") as img_file:
                        img_file.write(image_data)

                    logger.debug(f"Saved image: {image_path}")

                except Exception as img_e:
                    logger.error(f"Failed to extract image {img_index + 1} on page {page_index + 1}: {img_e}")
                finally:
                    # Clean up resources
                    if base_image:
                        base_image = None

        except Exception as e:
            logger.error(f"Error extracting images from page {page_index + 1}: {e}")