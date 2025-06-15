# services/database_operations.py - POLISHED VERSION
"""Database operations service layer for document processing workflow"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import asdict
from pathlib import Path
from app.config.database import get_redis_manager, get_supabase_manager
from model.RAG_Summarize import EnhancedRAGSummarizer

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Service class for handling document processing workflow"""

    def __init__(self):
        self.redis_manager = get_redis_manager()
        self.supabase_manager = get_supabase_manager()
        self.summarizer = EnhancedRAGSummarizer()

    def _safe_log_to_supabase(self, session_id: str, operation: str, status: str, metadata: Dict = None):
        """Safely log to Supabase without failing the main operation"""
        try:
            self.supabase_manager.create_processing_log(session_id, operation, status, metadata or {})
        except Exception as e:
            logger.warning(f"Failed to log {operation}:{status} for session {session_id}: {e}")

    def _extract_text_content(self, document_data: dict) -> str:
        """Extract the best available text content from document data"""
        text_fields = ["cleaned_text", "polished_text", "original_cleaned_text"]

        for field in text_fields:
            text = document_data.get(field, "")
            if text and len(text.strip()) > 0:
                logger.info(f"Using {field}: {len(text)} characters")
                return text

        # Log available fields for debugging
        logger.error(f"No valid text content found in fields: {text_fields}")
        logger.error(f"Available keys: {list(document_data.keys())}")
        return ""

    def _validate_document_data(self, document_data: dict) -> None:
        """Validate required document data fields"""
        required_fields = ["session_id", "pdf_path"]
        missing_fields = [field for field in required_fields if not document_data.get(field)]

        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        text_content = self._extract_text_content(document_data)
        if not text_content:
            raise ValueError("No valid text content available - all text fields are empty")

    def save_cleaned_document(self, document_data: dict, table_name: str = "documents") -> str:
        """
        Unified method to save document to database

        Args:
            document_data: Document data dictionary
            table_name: Target table ("documents" or "cleaned_documents")

        Returns:
            Document ID from database
        """
        try:
            logger.info(f"Saving document to {table_name} with keys: {list(document_data.keys())}")

            # Validate input data
            self._validate_document_data(document_data)

            # Extract and prepare data
            text_content = self._extract_text_content(document_data)

            # Create database record
            db_record = {
                "session_id": document_data["session_id"],
                "pdf_path": document_data.get("pdf_path") or document_data.get("file_path"),
                "original_cleaned_text": text_content,
                "combined_summary": document_data.get("combined_summary", ""),
                "metadata": document_data.get("metadata", {}),
                "summarized_pages": document_data.get("summarized_pages") or document_data.get("polished_pages", {}),
                "image_analysis": document_data.get("image_analysis", {}),
                "created_at": document_data.get("created_at") or datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            logger.info(f"Saving to {table_name} with text length: {len(text_content)}")

            # Save to appropriate table
            if table_name == "cleaned_documents":
                response = self.supabase_manager.create_cleaned_document_record(db_record)
            else:
                response = self.supabase_manager.create_document_record(db_record)

            if response and response.get("id"):
                document_id = response["id"]
                logger.info(f"Document saved successfully to {table_name} with ID: {document_id}")
                return document_id
            else:
                logger.error(f"Database save failed - response: {response}")
                raise ValueError(f"Failed to save document to {table_name}")

        except Exception as e:
            logger.error(f"Error saving document to {table_name}: {e}")
            # Log sample content for debugging
            if document_data:
                for key in ["cleaned_text", "polished_text", "original_cleaned_text"]:
                    value = document_data.get(key, "")
                    if value:
                        logger.info(f"Sample {key} (first 200 chars): {value[:200]}")
            raise

    def store_processing_result(self, session_id: str, processing_result: Dict[str, Any]) -> bool:
        """Store processing result in Redis cache"""
        try:
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

            # Store the full processing result with 2-hour TTL
            success = self.redis_manager.set_processing_data(session_id, processing_result, ttl=7200)

            if success:
                logger.info(f"Processing result stored in Redis for session {session_id}")
                self._safe_log_to_supabase(
                    session_id, "pdf_processing", "completed",
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

    def _prepare_summarization_input(self, session_id: str, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data structure for summarization"""
        return {
            "session_id": session_id,
            "cleaned_text": processing_result.get("cleaned_text", ""),
            "polished_text": processing_result.get("polished_text", ""),
            "polished_pages": processing_result.get("polished_pages", {}),
            "pdf_path": processing_result.get("pdf_path"),
            "metadata": {
                "filename": f"{session_id}.pdf",
                "processing_timestamp": datetime.now().isoformat(),
                "original_pdf_path": processing_result.get("pdf_path")
            },
            "image_analysis": {}
        }

    def process_and_summarize(self, session_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Process cached data through summarization pipeline"""
        try:
            self.redis_manager.set_session_status(session_id, "summarizing")

            # Get and validate processing result
            processing_result = self.get_processing_result(session_id)
            if not processing_result:
                error_msg = "Processing result not found in cache"
                logger.error(f"{error_msg} for session {session_id}")
                return False, {"error": error_msg}

            if not processing_result.get("success"):
                error_msg = "Original processing failed"
                logger.error(f"{error_msg} for session {session_id}")
                return False, {"error": error_msg}

            # Log summarization start
            pages_count = len(processing_result.get("polished_pages", {}))
            self._safe_log_to_supabase(
                session_id, "summarization", "started",
                {"pages_to_summarize": pages_count}
            )

            # Prepare and process summarization
            summarization_input = self._prepare_summarization_input(session_id, processing_result)
            logger.info(f"Starting summarization for session {session_id}")

            summarized_doc = self.summarizer.process_document(summarization_input)
            logger.info(f"Summarization completed for session {session_id}")

            # Log completion
            self._safe_log_to_supabase(
                session_id, "summarization", "completed",
                {
                    "pages_summarized": len(summarized_doc.summarized_pages),
                    "combined_summary_length": len(summarized_doc.combined_summary)
                }
            )

            return True, asdict(summarized_doc)

        except Exception as e:
            error_msg = f"Summarization failed: {str(e)}"
            logger.error(f"{error_msg} for session {session_id}")
            self._safe_log_to_supabase(session_id, "summarization", "failed", {"error": str(e)})
            return False, {"error": error_msg}

    def save_to_database(self, session_id: str, summarized_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Save summarized document to Supabase database"""
        try:
            self.redis_manager.set_session_status(session_id, "saving_to_database")
            self._safe_log_to_supabase(session_id, "database_save", "started")

            # Use unified save method
            document_id = self.save_document(summarized_data, table_name="documents")

            logger.info(f"Document saved to database with ID {document_id} for session {session_id}")

            # Update status and log completion
            self.redis_manager.set_session_status(session_id, "completed", {"document_id": document_id})
            self._safe_log_to_supabase(
                session_id, "database_save", "completed",
                {"document_id": document_id}
            )

            return True, document_id

        except Exception as e:
            error_msg = f"Database save failed: {str(e)}"
            logger.error(f"{error_msg} for session {session_id}")
            self._safe_log_to_supabase(session_id, "database_save", "failed", {"error": str(e)})
            return False, None

    def cleanup_cache(self, session_id: str) -> bool:
        """Clean up Redis cache after successful database save"""
        try:
            # Delete processing data but keep status for client polling
            processing_deleted = self.redis_manager.delete_processing_data(session_id)
            logger.info(f"Cache cleanup completed for session {session_id}")
            return processing_deleted
        except Exception as e:
            logger.error(f"Cache cleanup failed for session {session_id}: {e}")
            return False

    def complete_workflow(self, session_id: str) -> Dict[str, Any]:
        """Complete the entire workflow: process, summarize, save, cleanup"""
        workflow_start = datetime.now()

        try:
            logger.info(f"Starting complete workflow for session {session_id}")

            # Step 1: Process and summarize
            success, summarized_data = self.process_and_summarize(session_id)
            if not success:
                return self._create_workflow_result(
                    False, session_id, workflow_start,
                    error=summarized_data.get("error", "Summarization failed")
                )

            # Step 2: Save to database
            logger.info(f"Saving to database for session {session_id}")
            save_success, document_id = self.save_to_database(session_id, summarized_data)
            if not save_success:
                return self._create_workflow_result(
                    False, session_id, workflow_start,
                    error="Failed to save to database"
                )

            # Step 3: Cleanup cache
            logger.info(f"Cleaning up cache for session {session_id}")
            self.cleanup_cache(session_id)

            # Create success result
            workflow_duration = (datetime.now() - workflow_start).total_seconds()
            pages_processed = len(summarized_data.get("summarized_pages", []))

            self._safe_log_to_supabase(
                session_id, "workflow", "completed",
                {
                    "document_id": document_id,
                    "duration_seconds": workflow_duration,
                    "pages_processed": pages_processed
                }
            )

            return {
                "success": True,
                "document_id": document_id,
                "session_id": session_id,
                "workflow_duration": workflow_duration,
                "pages_processed": pages_processed,
                "combined_summary": summarized_data.get("combined_summary", ""),
                "message": "Workflow completed successfully"
            }

        except Exception as e:
            error_msg = f"Workflow failed: {str(e)}"
            logger.error(f"{error_msg} for session {session_id}")
            self._safe_log_to_supabase(session_id, "workflow", "failed", {"error": str(e)})
            return self._create_workflow_result(False, session_id, workflow_start, error=error_msg)

    def _create_workflow_result(self, success: bool, session_id: str, start_time: datetime,
                                error: str = None, **kwargs) -> Dict[str, Any]:
        """Helper to create consistent workflow result structure"""
        result = {
            "success": success,
            "session_id": session_id,
            "workflow_duration": (datetime.now() - start_time).total_seconds(),
            **kwargs
        }
        if error:
            result["error"] = error
        return result

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current session processing status"""
        try:
            redis_status = self.redis_manager.get_session_status(session_id)

            status_info = {
                "session_id": session_id,
                "redis_status": redis_status,
                "database_saved": False,
                "document_id": None,
                "current_status": redis_status.get("status", "unknown") if redis_status else "not_found",
                "last_update": redis_status.get("timestamp") if redis_status else None,
                "metadata": redis_status.get("metadata", {}) if redis_status else {}
            }

            # Try to get document from database
            try:
                db_document = self.supabase_manager.get_document_by_session(session_id)
                if db_document:
                    status_info.update({
                        "database_saved": True,
                        "document_id": db_document.get("id")
                    })
            except Exception as db_error:
                logger.warning(f"Could not check database for session {session_id}: {db_error}")

            return status_info

        except Exception as e:
            logger.error(f"Failed to get session status for {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "current_status": "error"
            }

    def get_document_by_session(self, session_id: str, table_name: str = "documents") -> Optional[Dict[str, Any]]:
        """Get saved document by session ID from specified table"""
        try:
            if table_name == "cleaned_documents":
                return self.supabase_manager.get_cleaned_document_by_session(session_id)
            else:
                return self.supabase_manager.get_document_by_session(session_id)
        except Exception as e:
            logger.error(f"Failed to get document from {table_name} for session {session_id}: {e}")
            return None

    def update_document(self, session_id: str, updates: dict, table_name: str = "documents") -> Optional[
        Dict[str, Any]]:
        """Update document in specified table"""
        try:
            updates['updated_at'] = datetime.now().isoformat()

            if table_name == "cleaned_documents":
                return self.supabase_manager.update_cleaned_document(session_id, updates)
            else:
                return self.supabase_manager.update_document(session_id, updates)
        except Exception as e:
            logger.error(f"Failed to update document in {table_name} for session {session_id}: {e}")
            return None

    def list_documents(self, limit: int = 50, offset: int = 0, table_name: str = "documents") -> List[Dict[str, Any]]:
        """List documents from specified table with pagination"""
        try:
            if table_name == "cleaned_documents":
                return self.supabase_manager.list_cleaned_documents(limit, offset)
            else:
                return self.supabase_manager.list_documents(limit, offset)
        except Exception as e:
            logger.error(f"Failed to list documents from {table_name}: {e}")
            return []

    def delete_document(self, session_id: str) -> bool:
        """Delete document and cleanup all related data from both tables"""
        try:
            operations = [
                ("main_database", lambda: self.supabase_manager.delete_document(session_id)),
                ("cleaned_database", lambda: self.supabase_manager.delete_cleaned_document(session_id)),
                ("cache", lambda: self.cleanup_cache(session_id)),
                ("status", lambda: self.redis_manager.delete_cache(f"status:{session_id}"))
            ]

            results = []
            for name, operation in operations:
                try:
                    results.append(operation())
                except Exception as e:
                    logger.warning(f"{name.capitalize()} deletion failed for session {session_id}: {e}")
                    results.append(False)

            success = any(results)
            if success:
                logger.info(f"Document and related data deleted for session {session_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to delete document for session {session_id}: {e}")
            return False

    def save_cleaned_document_new_table(self, document_data: dict) -> str:
        """Save cleaned document to the new cleaned_documents table"""
        try:
            # Log what we received
            logger.info(f"Saving cleaned document with data keys: {list(document_data.keys())}")

            # Extract text content
            cleaned_text = document_data.get("cleaned_text", "")
            polished_text = document_data.get("polished_text", "")
            original_cleaned_text = document_data.get("original_cleaned_text", "")

            # Use the best available text content
            final_cleaned_text = cleaned_text or original_cleaned_text or polished_text

            if not final_cleaned_text:
                logger.error(f"No text content found in document_data: {list(document_data.keys())}")
                raise ValueError("No cleaned text available to save - all text fields are empty")

            # Prepare record for cleaned_documents table
            db_record = {
                "session_id": document_data.get("session_id"),
                "original_filename": Path(document_data.get("pdf_path", "")).name,
                "pdf_path": document_data.get("pdf_path") or document_data.get("file_path"),

                # Main content fields
                "cleaned_text": final_cleaned_text,
                "polished_text": polished_text or None,

                # Processing results
                "polished_pages": document_data.get("polished_pages", {}),
                "image_analysis": document_data.get("image_analysis", {}),

                # Metadata
                "metadata": document_data.get("metadata", {}),
                "file_size": document_data.get("metadata", {}).get("file_size"),
                "pages_processed": len(document_data.get("polished_pages", {})),

                # Status
                "processing_status": "completed",

                # Timestamps
                "created_at": document_data.get("created_at") or datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            # Validate essential fields
            required_fields = ["session_id", "pdf_path", "cleaned_text"]
            for field in required_fields:
                if not db_record.get(field):
                    raise ValueError(f"{field} is required but missing or empty")

            # Log what we're saving
            logger.info(f"Saving cleaned document - text length: {len(db_record['cleaned_text'])}")
            logger.info(f"Database record keys: {list(db_record.keys())}")

            # Save to cleaned_documents table
            logger.info(
                f"Calling supabase_manager.create_cleaned_document_record for session {db_record.get('session_id')}")
            response = self.supabase_manager.create_cleaned_document_record(db_record)

            if response:
                document_id = response.get("id")
                logger.info(f"Cleaned document saved successfully with ID: {document_id}")
                return document_id
            else:
                raise ValueError("Failed to save cleaned document - no response data")

        except Exception as e:
            logger.error(f"Error saving cleaned document: {e}")
            logger.error(f"Document data available: {list(document_data.keys()) if document_data else 'None'}")
            raise

    def get_cleaned_document_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cleaned document by session ID"""
        try:
            return self.supabase_manager.get_cleaned_document_by_session(session_id)
        except Exception as e:
            logger.error(f"Failed to get cleaned document for session {session_id}: {e}")
            return None


# Global service instance
_service_instance = None


def get_document_service() -> DocumentProcessingService:
    """Get document processing service singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = DocumentProcessingService()
    return _service_instance