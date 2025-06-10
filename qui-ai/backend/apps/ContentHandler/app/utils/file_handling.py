# utils/file_handling.py
import os
import os
import logging
from pathlib import Path
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Configs (could move to separate config.py)
UPLOAD_DIR = "static/uploads"
ALLOWED_EXTENSIONS = {'.pdf', '.PDF'}
MAX_FILE_SIZE = 100 * 1024 * 1024


def create_base_directories():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Add other directories as needed


def validate_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Only PDFs allowed. Got: {file_ext}")

def get_relative_path(full_path: str) -> str:
    """Convert absolute path to static-relative path"""
    return os.path.relpath(full_path, "static").replace("\\", "/")


def create_session_directories(session_id: str) -> dict:
    """Create all required directories for a session"""
    paths = {
        "upload": os.path.join("static", "uploads", session_id),
        "processed": os.path.join("static", "processed", session_id),
        "images": os.path.join("static", "images", session_id)
    }

    for path in paths.values():
        os.makedirs(path, exist_ok=True)

    return paths