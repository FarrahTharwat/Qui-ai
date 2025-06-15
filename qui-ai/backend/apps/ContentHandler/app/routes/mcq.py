# app/routes/mcq.py
"""MCQ generation API routes"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.mcq_service import mcq_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/mcq", tags=["MCQ Generation"])


# Pydantic models for request/response
class MCQGenerationRequest(BaseModel):
    document_id: str = Field(..., description="ID of the document to generate MCQs from")
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")


class MCQUpdateRequest(BaseModel):
    question: Optional[str] = Field(None, description="Updated question text")
    distractor1: Optional[str] = Field(None, description="First distractor option")
    distractor2: Optional[str] = Field(None, description="Second distractor option")
    distractor3: Optional[str] = Field(None, description="Third distractor option")
    correct_answer: Optional[str] = Field(None, description="Correct answer")


class MCQResponse(BaseModel):
    id: str
    question: str
    distractor1: str
    distractor2: str
    distractor3: str
    correct_answer: str
    document_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MCQGenerationResponse(BaseModel):
    success: bool
    session_id: str
    message: str
    mcq_count: Optional[int] = None
    statistics: Optional[Dict[str, Any]] = None


class ProcessingStatusResponse(BaseModel):
    session_id: str
    status: str  # processing, completed, failed
    stage: str
    progress: int  # 0-100
    mcq_count: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None


async def _generate_mcqs_background(document_identifier: str, session_id: str):
    """
    Background task to generate MCQs from a document

    Args:
        document_identifier: Could be document_id or session_id
        session_id: Session identifier for tracking
    """
    try:
        await mcq_service.generate_mcqs_from_document(document_identifier, session_id)
    except Exception as e:
        logger.error(f"Background MCQ generation failed: {e}")


@router.post("/generate/{document_id}", response_model=MCQGenerationResponse)
async def generate_mcqs(
        document_id: str,
        background_tasks: BackgroundTasks,
        session_id: Optional[str] = Query(None, description="Optional session ID for tracking")
):
    """
    Generate MCQs from a document's cleaned text using T5 + RoBERTa models
    """
    try:
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"Starting MCQ generation for document {document_id}, session {session_id}")

        # Start background task - pass document_id which might actually be a session_id
        background_tasks.add_task(
            _generate_mcqs_background,
            document_id,  # This might actually be a session_id that needs to be resolved
            session_id  # Keep session_id for tracking
        )

        return MCQGenerationResponse(
            success=True,
            session_id=session_id,
            message="MCQ generation started. Use the session_id to check progress.",
        )

    except Exception as e:
        logger.error(f"Error starting MCQ generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start MCQ generation: {str(e)}")


@router.get("/status/{session_id}", response_model=ProcessingStatusResponse)
async def get_generation_status(session_id: str):
    """
    Get the status of MCQ generation process

    Returns current progress, stage, and any results or errors.
    """
    try:
        status = mcq_service.get_processing_status(session_id)

        if not status:
            raise HTTPException(status_code=404, detail="Session not found")

        return ProcessingStatusResponse(
            session_id=session_id,
            status=status.get("status", "unknown"),
            stage=status.get("stage", "unknown"),
            progress=status.get("progress", 0),
            mcq_count=status.get("mcq_count"),
            error=status.get("error"),
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at"),
            failed_at=status.get("failed_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/document/{document_id}", response_model=List[MCQResponse])
async def get_mcqs_by_document(document_id: str):
    """
    Get all MCQs generated for a specific document

    Returns a list of all MCQs associated with the document.
    """
    try:
        mcqs = await mcq_service.get_mcqs_by_document(document_id)

        return [
            MCQResponse(
                id=str(mcq.get("id")),
                question=mcq.get("question", ""),
                distractor1=mcq.get("distractor1", ""),
                distractor2=mcq.get("distractor2", ""),
                distractor3=mcq.get("distractor3", ""),
                correct_answer=mcq.get("correct_answer", ""),
                document_id=mcq.get("document_id", ""),
                created_at=mcq.get("created_at"),
                updated_at=mcq.get("updated_at")
            )
            for mcq in mcqs
        ]

    except Exception as e:
        logger.error(f"Error fetching MCQs for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch MCQs: {str(e)}")


@router.get("/{mcq_id}", response_model=MCQResponse)
async def get_mcq(mcq_id: str):
    """
    Get a specific MCQ by ID

    Returns the complete MCQ with all options and metadata.
    """
    try:
        mcq = await mcq_service.get_mcq_by_id(mcq_id)

        if not mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        return MCQResponse(
            id=str(mcq.get("id")),
            question=mcq.get("question", ""),
            distractor1=mcq.get("distractor1", ""),
            distractor2=mcq.get("distractor2", ""),
            distractor3=mcq.get("distractor3", ""),
            correct_answer=mcq.get("correct_answer", ""),
            document_id=mcq.get("document_id", ""),
            created_at=mcq.get("created_at"),
            updated_at=mcq.get("updated_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching MCQ {mcq_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch MCQ: {str(e)}")


@router.put("/{mcq_id}", response_model=MCQResponse)
async def update_mcq(mcq_id: str, updates: MCQUpdateRequest):
    """
    Update a specific MCQ

    Allows updating question, distractors, and correct answer.
    Only provided fields will be updated.
    """
    try:
        # Convert to dict and filter None values
        update_data = {k: v for k, v in updates.dict().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No valid updates provided")

        updated_mcq = await mcq_service.update_mcq(mcq_id, update_data)

        if not updated_mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        return MCQResponse(
            id=str(updated_mcq.get("id")),
            question=updated_mcq.get("question", ""),
            distractor1=updated_mcq.get("distractor1", ""),
            distractor2=updated_mcq.get("distractor2", ""),
            distractor3=updated_mcq.get("distractor3", ""),
            correct_answer=updated_mcq.get("correct_answer", ""),
            document_id=updated_mcq.get("document_id", ""),
            created_at=updated_mcq.get("created_at"),
            updated_at=updated_mcq.get("updated_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating MCQ {mcq_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update MCQ: {str(e)}")


@router.delete("/{mcq_id}")
async def delete_mcq(mcq_id: str):
    """
    Delete a specific MCQ

    Permanently removes the MCQ from the database.
    """
    try:
        success = await mcq_service.delete_mcq(mcq_id)

        if not success:
            raise HTTPException(status_code=404, detail="MCQ not found")

        return {"success": True, "message": "MCQ deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting MCQ {mcq_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete MCQ: {str(e)}")


@router.delete("/document/{document_id}")
async def delete_mcqs_by_document(document_id: str):
    """
    Delete all MCQs for a specific document

    Permanently removes all MCQs associated with the document.
    """
    try:
        # Get all MCQs for the document
        mcqs = await mcq_service.get_mcqs_by_document(document_id)

        if not mcqs:
            return {"success": True, "message": "No MCQs found for document", "deleted_count": 0}

        # Delete each MCQ
        deleted_count = 0
        for mcq in mcqs:
            success = await mcq_service.delete_mcq(str(mcq.get("id")))
            if success:
                deleted_count += 1

        return {
            "success": True,
            "message": f"Deleted {deleted_count} MCQs for document",
            "deleted_count": deleted_count,
            "total_found": len(mcqs)
        }

    except Exception as e:
        logger.error(f"Error deleting MCQs for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete MCQs: {str(e)}")


@router.post("/cleanup/{session_id}")
async def cleanup_session(session_id: str):
    """
    Clean up session data

    Removes processing status data for the session.
    """
    try:
        mcq_service.cleanup_session(session_id)
        return {"success": True, "message": "Session cleaned up successfully"}

    except Exception as e:
        logger.error(f"Error cleaning up session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup session: {str(e)}")


@router.get("/statistics/{document_id}")
async def get_mcq_statistics(document_id: str):
    """
    Get statistics for MCQs generated from a document

    Returns comprehensive statistics about the MCQs including difficulty distribution,
    confidence scores, and other metrics.
    """
    try:
        mcqs = await mcq_service.get_mcqs_by_document(document_id)

        if not mcqs:
            return {
                "success": True,
                "document_id": document_id,
                "total_mcqs": 0,
                "message": "No MCQs found for this document"
            }

        # Generate statistics
        statistics = mcq_service._generate_statistics(mcqs)

        return {
            "success": True,
            "document_id": document_id,
            "statistics": statistics,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting MCQ statistics for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")