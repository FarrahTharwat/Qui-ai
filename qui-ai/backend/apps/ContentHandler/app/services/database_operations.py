# services/database_operations.py
"""Database operations service layer for document processing workflow"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import asdict
import uuid
import os

from app.config.database import get_redis_manager, get_supabase_manager
from model.RAG_Summarize import SummarizedDocument, EnhancedRAGSummarizer

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Service class for handling document processing workflow"""

    def __init__(self):
        self.redis_manager = get_redis_manager()
        self.supabase_manager = get_supabase_manager()
        self.summarizer = EnhancedRAGSummarizer()

    def store_processing_result(self, session_id: str, processing_result: Dict[str, Any]) -> bool:
        """Store processing result in Redis cache"""
        try:
            # Validate processing result
            if not processing_result.get("success"):
                logger.error(f"Processing failed for session {session_id}: {processing_result.get('error')}")
                return False

            # Set processing status
            self.redis_manager.set_session_status(
                session_id,
                "processed",
                {
                    "pdf_path": processing_result.get("pdf_path"),
                    "json_path": processing_result.get("json_path"),
                    "pages_count": len(processing_result.get("polished_pages", {}))
                }
            )

            # Store the full processing result
            success = self.redis_manager.set_processing_data(
                session_id,
                processing_result,
                ttl=7200  # 2 hours TTL for processing data
            )

            if success:
                logger.info(f"Processing result stored in Redis for session {session_id}")
                # Log processing completion
                self.supabase_manager.create_processing_log(
                    session_id,
                    "pdf_processing",
                    "completed",
                    {"pages_processed": len(processing_result.get("polished_pages", {}))}
                )

            return success

        except Exception as e:
            logger.error(f"Failed to store processing result for {session_id}: {e}")
            return False

    def get_processing_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve processing result from Redis cache"""
        try:
            result = self.redis_manager.get_processing_data(session_id)
            if result:
                logger.info(f"Processing result retrieved for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve processing result for {session_id}: {e}")
            return None

    def process_and_summarize(self, session_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Process cached data through summarization pipeline"""
        try:
            # Set status to summarizing
            self.redis_manager.set_session_status(session_id, "summarizing")

            # Get processing result from cache
            processing_result = self.get_processing_result(session_id)
            if not processing_result:
                logger.error(f"No processing result found in cache for session {session_id}")
                return False, {"error": "Processing result not found in cache"}

            if not processing_result.get("success"):
                logger.error(f"Processing was not successful for session {session_id}")
                return False, {"error": "Original processing failed"}

            # Log summarization start
            self.supabase_manager.create_processing_log(
                session_id,
                "summarization",
                "started",
                {"pages_to_summarize": len(processing_result.get("polished_pages", {}))}
            )

            # Prepare data for summarization
            summarization_input = {
                "session_id": session_id,
                "cleaned_text": processing_result.get("cleaned_text", ""),
                "polished_text": processing_result.get("polished_text", ""),
                "polished_pages": processing_result.get("polished_pages", {}),
                "pdf_path": processing_result.get("pdf_path"),
                "metadata": {
                    "filename": processing_result.get("session_id", "") + ".pdf",
                    "processing_timestamp": datetime.now().isoformat(),
                    "original_pdf_path": processing_result.get("pdf_path")
                },
                "image_analysis": {}  # Could be extended if image analysis is available
            }

            logger.info(f"Starting summarization for session {session_id}")

            # Process through RAG summarization
            try:
                summarized_doc = self.summarizer.process_document(summarization_input)
                logger.info(f"Summarization completed for session {session_id}")

                # Log summarization completion
                self.supabase_manager.create_processing_log(
                    session_id,
                    "summarization",
                    "completed",
                    {
                        "pages_summarized": len(summarized_doc.summarized_pages),
                        "combined_summary_length": len(summarized_doc.combined_summary)
                    }
                )

                return True, asdict(summarized_doc)

            except Exception as e:
                logger.error(f"Summarization failed for session {session_id}: {e}")

                # Log summarization failure
                self.supabase_manager.create_processing_log(
                    session_id,
                    "summarization",
                    "failed",
                    {"error": str(e)}
                )

                return False, {"error": f"Summarization failed: {str(e)}"}

        except Exception as e:
            logger.error(f"Process and summarize failed for session {session_id}: {e}")
            return False, {"error": f"Process and summarize failed: {str(e)}"}

    def save_to_database(self, session_id: str, summarized_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Save summarized document to Supabase database"""
        try:
            # Set status to saving
            self.redis_manager.set_session_status(session_id, "saving_to_database")

            # Log database save start
            self.supabase_manager.create_processing_log(
                session_id,
                "database_save",
                "started"
            )

            # Create document record in database
            db_record = self.supabase_manager.create_document_record(summarized_data)

            if db_record:
                document_id = db_record.get("id")
                logger.info(f"Document saved to database with ID {document_id} for session {session_id}")

                # Log database save completion
                self.supabase_manager.create_processing_log(
                    session_id,
                    "database_save",
                    "completed",
                    {"document_id": document_id}
                )

                # Update status to completed
                self.redis_manager.set_session_status(
                    session_id,
                    "completed",
                    {"document_id": document_id}
                )

                return True, document_id
            else:
                logger.error(f"Failed to create database record for session {session_id}")

                # Log database save failure
                self.supabase_manager.create_processing_log(
                    session_id,
                    "database_save",
                    "failed",
                    {"error": "Failed to create database record"}
                )

                return False, None

        except Exception as e:
            logger.error(f"Database save failed for session {session_id}: {e}")

            # Log database save failure
            self.supabase_manager.create_processing_log(
                session_id,
                "database_save",
                "failed",
                {"error": str(e)}
            )

            return False, None

    def cleanup_cache(self, session_id: str) -> bool:
        """Clean up Redis cache after successful database save"""
        try:
            # Delete processing data
            processing_deleted = self.redis_manager.delete_processing_data(session_id)

            # Keep status for a while for client polling
            # Don't delete status immediately

            logger.info(f"Cache cleanup completed for session {session_id}")
            return processing_deleted

        except Exception as e:
            logger.error(f"Cache cleanup failed for session {session_id}: {e}")
            return False

    def complete_workflow(self, session_id: str) -> Dict[str, Any]:
        """Complete the entire workflow: process, summarize, save, cleanup"""
        try:
            workflow_start = datetime.now()

            # Step 1: Process and summarize
            logger.info(f"Starting complete workflow for session {session_id}")
            success, summarized_data = self.process_and_summarize(session_id)

            if not success:
                return {
                    "success": False,
                    "error": summarized_data.get("error", "Summarization failed"),
                    "session_id": session_id,
                    "workflow_duration": (datetime.now() - workflow_start).total_seconds()
                }

            # Step 2: Save to database
            logger.info(f"Saving to database for session {session_id}")
            save_success, document_id = self.save_to_database(session_id, summarized_data)

            if not save_success:
                return {
                    "success": False,
                    "error": "Failed to save to database",
                    "session_id": session_id,
                    "workflow_duration": (datetime.now() - workflow_start).total_seconds()
                }

            # Step 3: Cleanup cache
            logger.info(f"Cleaning up cache for session {session_id}")
            self.cleanup_cache(session_id)

            workflow_end = datetime.now()
            workflow_duration = (workflow_end - workflow_start).total_seconds()

            # Log workflow completion
            self.supabase_manager.create_processing_log(
                session_id,
                "workflow",
                "completed",
                {
                    "document_id": document_id,
                    "duration_seconds": workflow_duration,
                    "pages_processed": len(summarized_data.get("summarized_pages", []))
                }
            )

            return {
                "success": True,
                "document_id": document_id,
                "session_id": session_id,
                "workflow_duration": workflow_duration,
                "pages_processed": len(summarized_data.get("summarized_pages", [])),
                "combined_summary": summarized_data.get("combined_summary", ""),
                "message": "Workflow completed successfully"
            }

        except Exception as e:
            logger.error(f"Complete workflow failed for session {session_id}: {e}")

            # Log workflow failure
            self.supabase_manager.create_processing_log(
                session_id,
                "workflow",
                "failed",
                {"error": str(e)}
            )

            return {
                "success": False,
                "error": f"Workflow failed: {str(e)}",
                "session_id": session_id,
                "workflow_duration": (datetime.now() - workflow_start).total_seconds()
            }

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current session processing status"""
        try:
            # Get status from Redis
            redis_status = self.redis_manager.get_session_status(session_id)

            # Get document from database if it exists
            db_document = self.supabase_manager.get_document_by_session(session_id)

            # Combine information
            status_info = {
                "session_id": session_id,
                "redis_status": redis_status,
                "database_saved": db_document is not None,
                "document_id": db_document.get("id") if db_document else None,
                "current_status": redis_status.get("status", "unknown"),
                "last_update": redis_status.get("timestamp"),
                "metadata": redis_status.get("metadata", {})
            }

            return status_info

        except Exception as e:
            logger.error(f"Failed to get session status for {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "current_status": "error"
            }

    def get_document_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get saved document by session ID"""
        try:
            return self.supabase_manager.get_document_by_session(session_id)
        except Exception as e:
            logger.error(f"Failed to get document for session {session_id}: {e}")
            return None

    def list_documents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all documents with pagination"""
        try:
            return self.supabase_manager.list_documents(limit, offset)
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

    def delete_document(self, session_id: str) -> bool:
        """Delete document and cleanup all related data"""
        try:
            # Delete from database
            db_deleted = self.supabase_manager.delete_document(session_id)

            # Delete from cache
            cache_deleted = self.cleanup_cache(session_id)

            # Delete status
            status_deleted = self.redis_manager.delete_cache(f"status:{session_id}")

            success = db_deleted or cache_deleted or status_deleted

            if success:
                logger.info(f"Document and related data deleted for session {session_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to delete document for session {session_id}: {e}")
            return False


# Global service instance
_service_instance = None


def get_document_service() -> DocumentProcessingService:
    """Get document processing service singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = DocumentProcessingService()
    return _service_instance