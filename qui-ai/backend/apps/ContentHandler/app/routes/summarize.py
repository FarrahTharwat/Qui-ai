# app/routes/summarization.py
"""RAG-based document summarization router"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.summarization_service import summarization_service
from model.RAG_Summarize import EnhancedRAGSummarizer, SummarizedDocument

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/summarization",
    tags=["summarization"],
    responses={404: {"description": "Not found"}},
)


# Pydantic models for request/response
class SummarizationRequest(BaseModel):
    session_id: str = Field(..., description="Session ID for the document")
    document_id: str = Field(..., description="Document ID to summarize")
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional configuration overrides"
    )


class PageSummary(BaseModel):
    page_number: int
    summary: str
    key_points: List[str]
    relevance_score: float
    semantic_similarity: float
    content_overlap: float
    context_boost: float
    original_text_length: int


class SummarizationResponse(BaseModel):
    success: bool
    session_id: str
    document_id: str
    combined_summary: str
    page_summaries: List[PageSummary]
    metadata: Dict[str, Any]
    processing_time: float
    timestamp: str


class SummarizationStatus(BaseModel):
    session_id: str
    document_id: str
    exists: bool
    valid: bool
    pages_count: int
    has_cleaned_text: bool
    can_summarize: bool
    timestamp: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_type: str
    timestamp: str


@router.post("/generate", response_model=SummarizationResponse)
async def generate_summary(
        request: SummarizationRequest,
        background_tasks: BackgroundTasks
):
    """
    Generate RAG-based summary for a document

    - **session_id**: Session identifier for the document
    - **document_id**: Unique document identifier
    - **config**: Optional configuration overrides for summarization
    """
    start_time = datetime.now()

    try:
        logger.info(
            f"Starting RAG summarization for session_id: {request.session_id}, document_id: {request.document_id}")

        # Validate request
        if not request.session_id or not request.document_id:
            raise HTTPException(
                status_code=400,
                detail="Both session_id and document_id are required"
            )

        # Check if document exists and is valid
        try:
            document_status = await summarization_service.check_document_status(
                request.session_id,
                request.document_id
            )

            if not document_status["exists"]:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found for session_id: {request.session_id}, document_id: {request.document_id}"
                )

            if not document_status["valid"]:
                raise HTTPException(
                    status_code=400,
                    detail="Document exists but is not valid for summarization (missing required fields or empty content)"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking document status: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error validating document: {str(e)}"
            )

        # Generate summary using RAG service
        try:
            summary_result = await summarization_service.generate_summary(
                session_id=request.session_id,
                document_id=request.document_id,
                config=request.config or {}
            )

            logger.info(f"RAG summarization completed for {request.document_id}")

        except Exception as e:
            logger.error(f"RAG summarization failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Summarization processing failed: {str(e)}"
            )

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()

        # Convert to response format
        page_summaries = [
            PageSummary(
                page_number=page["page_number"],
                summary=page["summary"],
                key_points=page["key_points"],
                relevance_score=page["relevance_score"],
                semantic_similarity=page["semantic_similarity"],
                content_overlap=page["content_overlap"],
                context_boost=page["context_boost"],
                original_text_length=len(page.get("original_text", ""))
            )
            for page in summary_result["page_summaries"]
        ]

        # Prepare response metadata
        response_metadata = {
            "summarization_metadata": summary_result.get("summarization_metadata", {}),
            "original_metadata": summary_result.get("original_metadata", {}),
            "document_stats": {
                "total_pages": len(page_summaries),
                "original_text_length": summary_result.get("original_text_length", 0),
                "combined_summary_length": len(summary_result["combined_summary"]),
                "total_key_points": sum(len(page.key_points) for page in page_summaries),
                "avg_relevance_score": sum(page.relevance_score for page in page_summaries) / len(
                    page_summaries) if page_summaries else 0,
                "processing_time_seconds": processing_time
            },
            "pdf_path": summary_result.get("pdf_path", ""),
            "image_analysis": summary_result.get("image_analysis")
        }

        response = SummarizationResponse(
            success=True,
            session_id=request.session_id,
            document_id=request.document_id,
            combined_summary=summary_result["combined_summary"],
            page_summaries=page_summaries,
            metadata=response_metadata,
            processing_time=processing_time,
            timestamp=datetime.now().isoformat()
        )

        # Store summary result in background (optional)
        background_tasks.add_task(
            summarization_service.store_summary_result,
            request.session_id,
            request.document_id,
            summary_result
        )

        logger.info(f"RAG summarization completed in {processing_time:.2f} seconds")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during RAG summarization: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status/{session_id}/{document_id}", response_model=SummarizationStatus)
async def get_summarization_status(session_id: str, document_id: str):
    """
    Check if a document exists and can be summarized using RAG
    """
    try:
        logger.info(f"Checking summarization status for session_id: {session_id}, document_id: {document_id}")

        status = await summarization_service.check_document_status(session_id, document_id)

        return SummarizationStatus(
            session_id=session_id,
            document_id=document_id,
            exists=status["exists"],
            valid=status["valid"],
            pages_count=status.get("pages_count", 0),
            has_cleaned_text=status.get("has_cleaned_text", False),
            can_summarize=status["exists"] and status["valid"],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error checking summarization status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error checking document status: {str(e)}"
        )


@router.get("/history/{session_id}")
async def get_summarization_history(session_id: str, limit: int = 10):
    """
    Get summarization history for a session
    """
    try:
        logger.info(f"Fetching summarization history for session_id: {session_id}")

        history = await summarization_service.get_summarization_history(session_id, limit)

        return {
            "success": True,
            "session_id": session_id,
            "history": history,
            "count": len(history),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching summarization history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching history: {str(e)}"
        )


@router.get("/document/{document_id}")
async def get_document_summary(document_id: str):
    """
    Get existing summary for a document if available
    """
    try:
        logger.info(f"Fetching existing summary for document_id: {document_id}")

        summary = await summarization_service.get_existing_summary(document_id)

        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"No summary found for document_id: {document_id}"
            )

        return {
            "success": True,
            "document_id": document_id,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching summary: {str(e)}"
        )


@router.delete("/document/{document_id}")
async def delete_document_summary(document_id: str):
    """
    Delete summary for a document
    """
    try:
        logger.info(f"Deleting summary for document_id: {document_id}")

        deleted = await summarization_service.delete_summary(document_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"No summary found to delete for document_id: {document_id}"
            )

        return {
            "success": True,
            "message": f"Summary deleted for document_id: {document_id}",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting summary: {str(e)}"
        )


@router.get("/config")
async def get_summarization_config():
    """
    Get current RAG summarization configuration
    """
    try:
        config = await summarization_service.get_current_config()

        return {
            "success": True,
            "config": config,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching summarization config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching config: {str(e)}"
        )


@router.post("/config")
async def update_summarization_config(config: Dict[str, Any]):
    """
    Update RAG summarization configuration
    """
    try:
        logger.info(f"Updating summarization config: {config}")

        updated_config = await summarization_service.update_config(config)

        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": updated_config,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error updating summarization config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating config: {str(e)}"
        )