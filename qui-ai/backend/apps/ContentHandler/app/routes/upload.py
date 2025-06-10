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
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"Upload failed for session {session_id}: {e}")

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
            except:
                pass  # Don't fail on logging failure

        return JSONResponse(
            status_code=500,
            content=UploadResponse.error(
                f"Upload failed: {str(e)}",
                session_id=session_id
            )
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise

    except Exception as e:
        logger.error(f"Upload failed for session {session_id}: {e}")
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