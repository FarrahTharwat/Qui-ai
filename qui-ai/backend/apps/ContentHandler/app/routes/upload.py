# app/api/upload.py
"""FastAPI upload endpoint with complete document processing workflow"""

import os
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
import aiofiles






# Import your services
from app.services.database_operations import get_document_service, DocumentProcessingService
from app.utils.ProcessAndGenerate import process_pdf_pipeline_fixed
from app.config.database import get_redis_manager, get_supabase_manager
from app.utils.ProcessAndGenerate import process_pdf_pipeline_fixed


# Configure logging
logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(prefix="/api/v1", tags=["document-processing"])

# Configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "processed")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50")) * 1024 * 1024  # 50MB default
ALLOWED_EXTENSIONS = {".pdf"}

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


class UploadResponse:
    """Response model for upload operations"""

    @staticmethod
    def success(session_id: str, message: str = "Upload successful", **kwargs):
        return {
            "success": True,
            "session_id": session_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

    @staticmethod
    def error(message: str, session_id: str = None, **kwargs):
        return {
            "success": False,
            "error": message,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }


def validate_file(file: UploadFile) -> bool:
    """Validate uploaded file"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size (this is approximate, actual size checked during upload)
    if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    return True


async def save_uploaded_file(file: UploadFile, session_id: str) -> str:
    """Save uploaded file to disk"""
    try:
        # Create session-specific directory
        session_dir = Path(UPLOAD_DIR) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Generate safe filename
        original_name = Path(file.filename).stem
        file_ext = Path(file.filename).suffix.lower()
        safe_filename = f"{original_name}_{session_id}{file_ext}"
        file_path = session_dir / safe_filename

        # Save file with size validation
        total_size = 0
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(8192):  # 8KB chunks
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    # Clean up partial file
                    await f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB"
                    )
                await f.write(chunk)

        logger.info(f"File saved: {file_path} ({total_size} bytes)")
        return str(file_path)

    except Exception as e:
        logger.error(f"File save failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")


# Improved version of the upload flow with better alignment

async def process_document_async(session_id: str, pdf_path: str, document_service: DocumentProcessingService):
    """Asynchronous document processing with improved error handling"""
    redis_manager = get_redis_manager()
    supabase_manager = get_supabase_manager()

    try:
        logger.info(f"Starting async processing for session {session_id}")

        # Set initial status - matches database_operations.py expectations
        redis_manager.set_session_status(session_id, "pdf_processing", {"pdf_path": pdf_path})

        # Create output directory
        output_dir = Path(PROCESSED_DIR) / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Log processing start
        supabase_manager.create_processing_log(
            session_id,
            "pdf_processing",  # Match your actual DB schema
            "started",
            {
                "pdf_path": pdf_path,
                "output_dir": str(output_dir)
            }
        )

        # Run the processing pipeline
        processing_result = await asyncio.get_event_loop().run_in_executor(
            None,
            process_pdf_pipeline_fixed,
            pdf_path,
            str(output_dir),
            session_id,
            True,  # save_json
            True,  # generate_pdf_output
            500,  # chunk_size
            5  # page_count_threshold
        )

        if not processing_result.get("success"):
            error_msg = processing_result.get('error', 'Unknown processing error')
            logger.error(f"Processing failed for session {session_id}: {error_msg}")

            # Log processing failure
            supabase_manager.create_processing_log(
                session_id,
                "pdf_processing",
                "failed",
                {"error": error_msg}
            )

            redis_manager.set_session_status(session_id, "failed", {"error": error_msg})
            return

        # Store processing result in cache - this aligns with database_operations.py
        if not document_service.store_processing_result(session_id, processing_result):
            error_msg = "Failed to store processing result in cache"
            logger.error(f"{error_msg} for session {session_id}")

            supabase_manager.create_processing_log(
                session_id,
                "cache_storage",
                "failed",
                {"error": error_msg}
            )

            redis_manager.set_session_status(session_id, "failed", {"error": error_msg})
            return

        # Complete the workflow (summarize + save to DB + cleanup)
        # This calls database_operations.py complete_workflow method
        workflow_result = document_service.complete_workflow(session_id)

        if workflow_result.get("success"):
            logger.info(f"Workflow completed successfully for session {session_id}")

            # Final status update - this might be redundant as complete_workflow sets it
            # but ensures consistency
            final_metadata = {
                "document_id": workflow_result.get("document_id"),
                "pages_processed": workflow_result.get("pages_processed"),
                "workflow_duration": workflow_result.get("workflow_duration")
            }

            # Only update if complete_workflow didn't already set to completed
            current_status = redis_manager.get_session_status(session_id)
            if current_status.get("status") != "completed":
                redis_manager.set_session_status(session_id, "completed", final_metadata)

        else:
            error_msg = workflow_result.get('error', 'Workflow failed')
            logger.error(f"Workflow failed for session {session_id}: {error_msg}")
            redis_manager.set_session_status(session_id, "failed", {"error": error_msg})

    except Exception as e:
        logger.error(f"Async processing failed for session {session_id}: {e}")

        # Log unexpected error
        supabase_manager.create_processing_log(
            session_id,
            "processing",
            "error",
            {"error": str(e), "error_type": "unexpected"}
        )

        redis_manager.set_session_status(session_id, "failed", {"error": str(e)})

    finally:
        # Clean up uploaded file only after processing is complete (success or failure)
        try:
            if Path(pdf_path).exists():
                Path(pdf_path).unlink()
                logger.info(f"Cleaned up uploaded file: {pdf_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up uploaded file {pdf_path}: {e}")
            # Log cleanup failure but don't fail the whole process
            supabase_manager.create_processing_log(
                session_id,
                "cleanup",
                "warning",
                {"error": str(e), "file_path": pdf_path}
            )


@router.post("/upload")
async def upload_and_process_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """
    Upload PDF document and start complete processing workflow

    Workflow:
    1. Upload & validate file
    2. Generate session ID
    3. Save file to disk
    4. Start background processing:
       - Extract & clean text
       - Cache processing result
       - Summarize with RAG
       - Save to Supabase database
       - Clean up cache
    5. Return session ID for status tracking
    """
    session_id = None

    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        logger.info(f"Starting upload for session {session_id}, file: {file.filename}")

        # Validate file
        validate_file(file)

        # Save uploaded file
        pdf_path = await save_uploaded_file(file, session_id)

        # Log upload completion with correct field names
        supabase_manager = get_supabase_manager()
        supabase_manager.create_processing_log(
            session_id,
            "upload",
            "completed",
            {
                "filename": file.filename,
                "file_size": Path(pdf_path).stat().st_size,
                "file_path": pdf_path
            }
        )

        # Set initial status
        redis_manager = get_redis_manager()
        redis_manager.set_session_status(
            session_id,
            "uploaded",
            {
                "filename": file.filename,
                "file_path": pdf_path,
                "next_step": "pdf_processing"
            }
        )

        # Start background processing
        background_tasks.add_task(
            process_document_async,
            session_id,
            pdf_path,
            document_service
        )

        logger.info(f"Background processing started for session {session_id}")

        return JSONResponse(
            status_code=202,  # Accepted
            content=UploadResponse.success(
                session_id=session_id,
                message="File uploaded successfully. Processing started in background.",
                filename=file.filename,
                status="uploaded",
                next_status="pdf_processing",
                status_endpoint=f"/api/v1/status/{session_id}"
            )
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors) - these should bubble up to FastAPI
        logger.warning(f"HTTP exception during upload for session {session_id}")
        raise

    except Exception as e:
        logger.error(f"Upload failed for session {session_id}: {e}")
        logger.exception("Full traceback:")  # This will log the full stack trace

        # Log upload failure if session_id exists
        if session_id:
            try:
                supabase_manager = get_supabase_manager()
                supabase_manager.create_processing_log(
                    session_id,
                    "upload",
                    "failed",
                    {"error": str(e), "filename": getattr(file, 'filename', 'unknown')}
                )
            except Exception as log_error:
                logger.error(f"Failed to log upload failure: {log_error}")

        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(
                f"Upload failed: {str(e)}",
                session_id=session_id
            )
        )


# Replace your /status endpoint in upload.py with this version:

@router.get("/status/{session_id}")
async def get_processing_status(
        session_id: str,
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """Get current processing status for a session"""
    try:
        logger.info(f"Getting status for session: {session_id}")

        # Add timeout to prevent hanging
        status_info = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                document_service.get_session_status,
                session_id
            ),
            timeout=5.0  # 5 second timeout
        )

        if status_info.get("error"):
            logger.warning(f"Status error for session {session_id}: {status_info.get('error')}")
            return JSONResponse(
                status_code=404,
                content=UploadResponse.error(
                    f"Session not found or error: {status_info.get('error')}",
                    session_id=session_id
                )
            )

        logger.info(f"Status retrieved successfully for session: {session_id}")
        return JSONResponse(
            content=UploadResponse.success(
                session_id=session_id,
                message="Status retrieved successfully",
                status=status_info.get("current_status"),
                redis_status=status_info.get("redis_status"),
                database_saved=status_info.get("database_saved"),
                document_id=status_info.get("document_id"),
                last_update=status_info.get("last_update"),
                metadata=status_info.get("metadata", {})
            )
        )

    except asyncio.TimeoutError:
        logger.error(f"Status retrieval timeout for session {session_id}")
        return JSONResponse(
            status_code=504,
            content=UploadResponse.error(
                "Status retrieval timed out - database query too slow",
                session_id=session_id
            )
        )
    except Exception as e:
        logger.error(f"Status retrieval failed for session {session_id}: {e}")
        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(
                f"Status retrieval failed: {str(e)}",
                session_id=session_id
            )
        )


@router.post("/upload-and-clean")
async def upload_and_clean_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """
    Upload PDF document and perform preprocessing/cleaning, then save to database

    Workflow:
    1. Upload & validate file
    2. Generate session ID
    3. Save file to disk
    4. Start background processing for cleaning:
       - Extract text from PDF
       - Clean and preprocess text using your existing pipeline
       - Save cleaned result to database
       - Cache cleaned result
    5. Return session ID and document ID for tracking
    """
    session_id = None

    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        logger.info(f"Starting upload and clean for session {session_id}, file: {file.filename}")

        # Validate file
        validate_file(file)

        # Save uploaded file
        pdf_path = await save_uploaded_file(file, session_id)

        # Log upload completion
        supabase_manager = get_supabase_manager()
        supabase_manager.create_processing_log(
            session_id,
            "upload_and_clean",
            "started",
            {
                "filename": file.filename,
                "file_size": os.path.getsize(pdf_path),  # Use os.path.getsize instead of Path
                "file_path": pdf_path
            }
        )

        # Set initial status
        redis_manager = get_redis_manager()
        redis_manager.set_session_status(
            session_id,
            "uploaded",
            {
                "filename": file.filename,
                "file_path": pdf_path,
                "next_step": "cleaning_and_saving",
                "processing_type": "clean_and_save"
            }
        )

        # Start background cleaning and saving process
        background_tasks.add_task(
            process_document_clean_and_save,
            session_id,
            pdf_path,
            document_service
        )

        logger.info(f"Background cleaning and saving started for session {session_id}")

        return JSONResponse(
            status_code=202,  # Accepted
            content=UploadResponse.success(
                session_id=session_id,
                message="File uploaded successfully. Cleaning, preprocessing, and database saving started.",
                filename=file.filename,
                status="uploaded",
                next_status="cleaning",
                status_endpoint=f"/api/v1/status/{session_id}"
            )
        )

    except HTTPException:
        logger.warning(f"HTTP exception during upload and clean for session {session_id}")
        raise

    except Exception as e:
        logger.error(f"Upload and clean failed for session {session_id}: {e}")
        logger.exception("Full traceback:")

        # Log failure if session_id exists
        if session_id:
            try:
                supabase_manager = get_supabase_manager()
                supabase_manager.create_processing_log(
                    session_id,
                    "upload_and_clean",
                    "failed",
                    {"error": str(e), "filename": getattr(file, 'filename', 'unknown')}
                )
            except Exception as log_error:
                logger.error(f"Failed to log upload and clean failure: {log_error}")

        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(
                f"Upload and clean failed: {str(e)}",
                session_id=session_id
            )
        )


async def process_document_clean_and_save(
        session_id: str,
        pdf_path: str,
        document_service: DocumentProcessingService
):
    """
    Background task for cleaning, preprocessing, and saving to database
    FIXED VERSION - saves to cleaned_documents table
    """
    supabase_manager = get_supabase_manager()
    redis_manager = get_redis_manager()
    document_id = None

    try:
        logger.info(f"Starting clean and save processing for session {session_id}")

        # Get filename using os.path to avoid Path import issues
        filename = os.path.basename(pdf_path)

        # Update status to processing
        redis_manager.set_session_status(
            session_id,
            "cleaning",
            {
                "filename": filename,
                "file_path": pdf_path,
                "step": "comprehensive_preprocessing",
                "processing_type": "clean_and_save"
            }
        )

        # Create output directory for this session
        output_dir = os.path.join("temp", "processing", session_id)
        os.makedirs(output_dir, exist_ok=True)

        # Log processing start
        supabase_manager.create_processing_log(
            session_id,
            "comprehensive_preprocessing",
            "started",
            {"pdf_path": pdf_path, "output_dir": output_dir}
        )

        # Use your existing pipeline function
        from app.utils.ProcessAndGenerate import process_pdf_pipeline_fixed

        pipeline_result = await asyncio.get_event_loop().run_in_executor(
            None,
            process_pdf_pipeline_fixed,
            pdf_path,
            output_dir,
            session_id,
            True,  # save_json
            False,  # generate_pdf_output (we don't need PDF for clean-only)
            500,  # chunk_size
            5  # page_count_threshold
        )

        if not pipeline_result.get("success", False):
            raise ValueError(f"Pipeline processing failed: {pipeline_result.get('error', 'Unknown error')}")

        # CRITICAL FIX: Log what we actually got from the pipeline
        logger.info(f"Pipeline result keys: {list(pipeline_result.keys())}")
        logger.info(f"Cleaned text length: {len(pipeline_result.get('cleaned_text', ''))}")
        logger.info(f"Polished text length: {len(pipeline_result.get('polished_text', ''))}")

        # Check if we have the expected text content
        cleaned_text = pipeline_result.get("cleaned_text", "")
        polished_text = pipeline_result.get("polished_text", "")

        if not cleaned_text and not polished_text:
            # Log the full pipeline result to debug
            logger.error(f"No text content found in pipeline result: {pipeline_result}")
            raise ValueError("Pipeline processing completed but no text content was extracted")

        # Log processing completion
        supabase_manager.create_processing_log(
            session_id,
            "comprehensive_preprocessing",
            "completed",
            {
                "cleaned_text_length": len(cleaned_text),
                "polished_text_length": len(polished_text),
                "pages_processed": len(pipeline_result.get("polished_pages", {})),
                "json_path": pipeline_result.get("json_path"),
                "pipeline_result_keys": list(pipeline_result.keys())  # Debug info
            }
        )

        # Update status for database saving
        redis_manager.set_session_status(
            session_id,
            "saving_to_database",
            {
                "filename": filename,
                "file_path": pdf_path,
                "step": "saving_cleaned_document",
                "processing_type": "clean_and_save",
                "preprocessing_completed": True,
                "pages_processed": len(pipeline_result.get("polished_pages", {}))
            }
        )

        # FIXED: Prepare document data for cleaned_documents table using os.path
        file_size = os.path.getsize(pdf_path)

        document_data = {
            "session_id": session_id,
            "original_filename": filename,
            "pdf_path": pdf_path,

            # Main text content for cleaned_documents table
            "cleaned_text": cleaned_text or polished_text,  # Required field
            "polished_text": polished_text,  # Optional field

            # Processing results
            "polished_pages": pipeline_result.get("polished_pages", {}),
            "image_analysis": pipeline_result.get("image_analysis", {}),

            # Metadata
            "metadata": {
                "processing_timestamp": datetime.utcnow().isoformat(),
                "original_pdf_path": pdf_path,
                "original_filename": filename,
                "cleaned_text_length": len(cleaned_text),
                "polished_text_length": len(polished_text),
                "pages_processed": len(pipeline_result.get("polished_pages", {})),
                "pipeline_success": pipeline_result.get("success", False),
                "file_size": file_size,
                "pipeline_result_keys": list(pipeline_result.keys())
            },
            "file_size": file_size,
            "pages_processed": len(pipeline_result.get("polished_pages", {})),
            "processing_status": "completed",
            "created_at": datetime.utcnow().isoformat()
        }

        # VALIDATION: Ensure we have content to save
        if not document_data["cleaned_text"]:
            logger.error(f"No cleaned text available for session {session_id}")
            logger.error(f"Pipeline result: {pipeline_result}")
            raise ValueError("No cleaned text available to save to database")

        # FIXED: Save to cleaned_documents table using the new method
        try:
            supabase_manager.create_processing_log(
                session_id,
                "cleaned_database_save",
                "started",
                {
                    "target_table": "cleaned_documents",
                    "document_data_keys": list(document_data.keys()),
                    "cleaned_text_length": len(document_data["cleaned_text"]),
                    "has_polished_text": bool(document_data.get("polished_text"))
                }
            )

            # Use the NEW method for cleaned documents table
            document_id = document_service.save_cleaned_document_new_table(document_data)

            supabase_manager.create_processing_log(
                session_id,
                "cleaned_database_save",
                "completed",
                {
                    "document_id": document_id,
                    "table": "cleaned_documents"
                }
            )

            logger.info(
                f"Cleaned document saved to cleaned_documents table with ID {document_id} for session {session_id}")

        except Exception as db_error:
            logger.error(f"Cleaned document database save failed for session {session_id}: {db_error}")
            supabase_manager.create_processing_log(
                session_id,
                "cleaned_database_save",
                "failed",
                {"error": str(db_error), "table": "cleaned_documents"}
            )
            raise ValueError(f"Cleaned document database save failed: {str(db_error)}")

        # Update status for caching
        redis_manager.set_session_status(
            session_id,
            "caching_results",
            {
                "filename": filename,
                "file_path": pdf_path,
                "step": "caching_results",
                "processing_type": "clean_and_save",
                "preprocessing_completed": True,
                "database_saved": True,
                "document_id": document_id,
                "pages_processed": len(pipeline_result.get("polished_pages", {}))
            }
        )

        # Prepare structured result for caching (include document_id)
        structured_result = {
            "session_id": session_id,
            "document_id": document_id,  # This is now from cleaned_documents table
            "cleaned_text": cleaned_text,
            "polished_text": polished_text,
            "polished_pages": pipeline_result.get("polished_pages", {}),
            "pdf_path": pdf_path,
            "json_path": pipeline_result.get("json_path"),
            "metadata": {
                "filename": f"{session_id}.pdf",
                "processing_timestamp": datetime.utcnow().isoformat(),
                "original_pdf_path": pdf_path,
                "original_filename": filename,
                "cleaned_text_length": len(cleaned_text),
                "polished_text_length": len(polished_text),
                "pages_processed": len(pipeline_result.get("polished_pages", {})),
                "pipeline_success": pipeline_result.get("success", False),
                "document_id": document_id,
                "database_saved": True,
                "table_used": "cleaned_documents"  # Add this for clarity
            },
            "image_analysis": pipeline_result.get("image_analysis", {})
        }

        # Cache structured result
        supabase_manager.create_processing_log(
            session_id,
            "caching",
            "started",
            {"cache_type": "comprehensive_clean_result_with_db"}
        )

        cache_key = f"cleaned_result:{session_id}"
        redis_manager.cache_processing_result(
            cache_key,
            structured_result,
            ttl=3600  # Cache for 1 hour
        )

        supabase_manager.create_processing_log(
            session_id,
            "caching",
            "completed",
            {"cache_key": cache_key, "document_id": document_id}
        )

        # Final status update with both session_id and document_id
        redis_manager.set_session_status(
            session_id,
            "completed_clean_and_saved",
            {
                "filename": filename,
                "file_path": pdf_path,
                "processing_type": "clean_and_save",
                "cleaned_text_length": len(cleaned_text),
                "polished_text_length": len(polished_text),
                "pages_processed": len(pipeline_result.get("polished_pages", {})),
                "cache_key": cache_key,
                "json_path": pipeline_result.get("json_path"),
                "document_id": document_id,
                "database_saved": True,
                "completed_at": datetime.utcnow().isoformat(),
                "next_step": "ready_for_use"
            }
        )

        # Log overall completion
        supabase_manager.create_processing_log(
            session_id,
            "clean_and_save_processing",
            "completed",
            {
                "final_status": "completed_clean_and_saved",
                "cleaned_text_length": len(cleaned_text),
                "polished_text_length": len(polished_text),
                "pages_processed": len(pipeline_result.get("polished_pages", {})),
                "cache_key": cache_key,
                "json_path": pipeline_result.get("json_path"),
                "document_id": document_id,
                "database_saved": True,
                "structured_result_keys": list(structured_result.keys())
            }
        )

        logger.info(f"Clean and save processing completed for session {session_id}, document ID: {document_id}")

    except Exception as e:
        logger.error(f"Clean and save processing failed for session {session_id}: {e}")
        logger.exception("Full traceback:")

        # Log failure
        supabase_manager.create_processing_log(
            session_id,
            "clean_and_save_processing",
            "failed",
            {"error": str(e), "document_id": document_id}
        )

        # Get filename safely for error status
        try:
            filename = os.path.basename(pdf_path)
        except:
            filename = "unknown_file"

        # Update status to failed
        redis_manager.set_session_status(
            session_id,
            "failed",
            {
                "filename": filename,
                "file_path": pdf_path,
                "processing_type": "clean_and_save",
                "error": str(e),
                "document_id": document_id,
                "failed_at": datetime.utcnow().isoformat()
            }
        )

        raise  # Re-raise to ensure proper error handling


# Additional endpoint to get both session_id and document_id from status
@router.get("/status/{session_id}/details")
async def get_session_details(session_id: str):
    """
    Get detailed status including document_id if available
    """
    try:
        redis_manager = get_redis_manager()
        status_data = redis_manager.get_session_status(session_id)

        if not status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "status": status_data.get("status"),
                "document_id": status_data.get("document_id"),
                "processing_type": status_data.get("processing_type"),
                "database_saved": status_data.get("database_saved", False),
                "details": status_data
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session details for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session details")
@router.get("/cleaned-result/{session_id}")
async def get_cleaned_result(session_id: str):
    """
    Retrieve structured cleaned result for a session (same format as _prepare_summarization_input)
    """
    try:
        redis_manager = get_redis_manager()

        # Get session status
        status = redis_manager.get_session_status(session_id)
        if not status:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if cleaning is completed
        if status.get("status") != "completed_clean":
            current_status = status.get("status", "unknown")
            return JSONResponse(
                status_code=202,
                content={
                    "session_id": session_id,
                    "status": current_status,
                    "message": f"Cleaning not completed yet. Current status: {current_status}"
                }
            )

        # Get cached structured result
        cache_key = f"cleaned_result:{session_id}"
        structured_result = redis_manager.get_cached_result(cache_key)

        if not structured_result:
            raise HTTPException(
                status_code=404,
                detail="Cleaned result not found in cache"
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "completed_clean",
                "result": structured_result
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve cleaned result for session {session_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve cleaned result: {str(e)}"}
        )
# ALSO: Add this temporary debug version to test immediately:

@router.get("/status-debug/{session_id}")
async def get_processing_status_debug(session_id: str):
    """Debug version of status endpoint"""
    try:
        # Test Redis directly
        redis_manager = get_redis_manager()

        # This might be where it's hanging - test with timeout
        redis_status = None
        try:
            # Test Redis with a simple operation
            redis_status = redis_manager.get_session_status(session_id)
        except Exception as e:
            return JSONResponse(
                content={
                    "debug": True,
                    "session_id": session_id,
                    "redis_error": str(e),
                    "message": "Redis operation failed"
                }
            )

        return JSONResponse(
            content={
                "debug": True,
                "session_id": session_id,
                "redis_status": redis_status,
                "message": "Debug endpoint working"
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "debug": True,
                "session_id": session_id,
                "error": str(e),
                "message": "Debug endpoint failed"
            }
        )


# Add this debug version to your upload.py to isolate the issue:

@router.get("/status-detailed-debug/{session_id}")
async def get_processing_status_detailed_debug(
        session_id: str,
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """Detailed debug version to isolate the hanging issue"""
    debug_steps = []

    try:
        debug_steps.append("1. Starting debug")

        # Test Redis directly (we know this works)
        debug_steps.append("2. Testing Redis...")
        redis_manager = get_redis_manager()
        redis_status = redis_manager.get_session_status(session_id)
        debug_steps.append(f"3. Redis completed: {redis_status}")

        # Test Supabase manager directly
        debug_steps.append("4. Testing Supabase...")
        supabase_manager = get_supabase_manager()
        debug_steps.append("5. Supabase manager obtained")

        # Test document service creation
        debug_steps.append("6. Testing document service...")
        # document_service is already injected, so this should work
        debug_steps.append("7. Document service ready")

        # This is where it likely hangs - let's test step by step
        debug_steps.append("8. About to call document_service.get_session_status...")

        # Try to call it with a timeout
        import asyncio
        try:
            status_info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    document_service.get_session_status,
                    session_id
                ),
                timeout=2.0  # Short timeout to isolate
            )
            debug_steps.append(f"9. Document service call completed: {status_info}")
        except asyncio.TimeoutError:
            debug_steps.append("9. TIMEOUT: document_service.get_session_status() is hanging!")
            return JSONResponse(
                content={
                    "debug": True,
                    "session_id": session_id,
                    "hanging_at": "document_service.get_session_status()",
                    "debug_steps": debug_steps,
                    "conclusion": "The hang is in DocumentProcessingService.get_session_status() method"
                }
            )
        except Exception as e:
            debug_steps.append(f"9. Error in document service call: {str(e)}")

        debug_steps.append("10. All tests completed successfully")

        return JSONResponse(
            content={
                "debug": True,
                "session_id": session_id,
                "redis_status": redis_status,
                "status_info": status_info if 'status_info' in locals() else None,
                "debug_steps": debug_steps,
                "conclusion": "All operations working normally"
            }
        )

    except Exception as e:
        debug_steps.append(f"Error at step: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "debug": True,
                "session_id": session_id,
                "error": str(e),
                "debug_steps": debug_steps,
                "conclusion": f"Failed at step: {len(debug_steps)}"
            }
        )


@router.get("/document/{session_id}")
async def get_processed_document(
        session_id: str,
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """Get the processed document by session ID"""
    try:
        document = document_service.get_document_by_session(session_id)

        if not document:
            return JSONResponse(
                status_code=404,
                content=UploadResponse.error(
                    "Document not found or not yet processed",
                    session_id=session_id
                )
            )

        return JSONResponse(
            content=UploadResponse.success(
                session_id=session_id,
                message="Document retrieved successfully",
                document=document
            )
        )

    except Exception as e:
        logger.error(f"Document retrieval failed for session {session_id}: {e}")
        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(
                f"Document retrieval failed: {str(e)}",
                session_id=session_id
            )
        )


# Replace your /documents endpoint in upload.py with this version:

@router.get("/documents")
async def list_all_documents(
        limit: int = 50,
        offset: int = 0,
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """List all processed documents with pagination"""
    try:
        logger.info(f"Starting document listing with limit={limit}, offset={offset}")

        # Add timeout to prevent hanging
        documents = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                document_service.list_documents,
                limit,
                offset
            ),
            timeout=10.0  # 10 second timeout for document listing
        )

        logger.info(f"Document listing completed: {len(documents)} documents found")

        return JSONResponse(
            content={
                "success": True,
                "message": f"Retrieved {len(documents)} documents",
                "documents": documents,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "count": len(documents)
                },
                "timestamp": datetime.now().isoformat()
            }
        )

    except asyncio.TimeoutError:
        logger.error(f"Document listing timeout: limit={limit}, offset={offset}")
        return JSONResponse(
            status_code=504,
            content=UploadResponse.error(
                "Document listing timed out - database query too slow",
                metadata={"limit": limit, "offset": offset}
            )
        )
    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(f"Document listing failed: {str(e)}")
        )


@router.delete("/document/{session_id}")
async def delete_document(
        session_id: str,
        document_service: DocumentProcessingService = Depends(get_document_service)
):
    """Delete document and all related data"""
    try:
        success = document_service.delete_document(session_id)

        if success:
            return JSONResponse(
                content=UploadResponse.success(
                    session_id=session_id,
                    message="Document and related data deleted successfully"
                )
            )
        else:
            return JSONResponse(
                status_code=404,
                content=UploadResponse.error(
                    "Document not found or deletion failed",
                    session_id=session_id
                )
            )

    except Exception as e:
        logger.error(f"Document deletion failed for session {session_id}: {e}")
        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(
                f"Document deletion failed: {str(e)}",
                session_id=session_id
            )
        )


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        redis_manager = get_redis_manager()
        redis_status = redis_manager.ping() if hasattr(redis_manager, 'ping') else True

        # Test Supabase connection
        supabase_manager = get_supabase_manager()
        supabase_status = True  # Add actual health check if available

        return JSONResponse(
            content={
                "success": True,
                "message": "Service is healthy",
                "services": {
                    "redis": "connected" if redis_status else "disconnected",
                    "supabase": "connected" if supabase_status else "disconnected"
                },
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content=UploadResponse.error(f"Service unhealthy: {str(e)}")
        )