# app/services/mcq_service.py
"""MCQ Generation Service using T5 + RoBERTa models with Supabase integration"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Import the MCQ generator functions
from app.core.mcq_generator import (
    generate_quality_mcqs_from_text,
    display_mcqs_enhanced
)

logger = logging.getLogger(__name__)
load = load_dotenv()

class MCQGenerationService:
    """Service for generating MCQs from document text and storing in Supabase"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.processing_status = {}

        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and ANON_KEY must be set in environment variables")

        self.supabase: Client = create_client(supabase_url, supabase_key)

    # Updated _find_document_id method and _save_mcqs_to_database method

    # If you update the schema to reference cleaned_documents, use this simpler version:
    async def _find_document_id(self, identifier: str) -> Optional[str]:
        """Find the cleaned document ID using session_id or document_id with detailed logging"""
        try:
            logger.info(f"Searching for document with identifier: {identifier}")

            # First, try to find document by session_id in cleaned_documents
            response = self.supabase.table("cleaned_documents").select("id, session_id").eq("session_id",
                                                                                            identifier).execute()

            if response.data:
                doc_id = response.data[0]['id']
                logger.info(f"Found cleaned document by session_id '{identifier}': {doc_id}")

                # Verify this ID actually exists (double-check)
                verify_response = self.supabase.table("cleaned_documents").select("id").eq("id", doc_id).execute()
                if verify_response.data:
                    logger.info(f"Verified document ID {doc_id} exists in cleaned_documents")
                    return doc_id
                else:
                    logger.error(f"Document ID {doc_id} verification failed!")
                    return None

            # If not found by session_id, check if the identifier is already a valid cleaned document ID
            response = self.supabase.table("cleaned_documents").select("id, session_id").eq("id", identifier).execute()

            if response.data:
                logger.info(
                    f"Found cleaned document by ID '{identifier}': session_id = {response.data[0].get('session_id')}")
                return response.data[0]["id"]

            # Debug: Let's see what's actually in the cleaned_documents table
            logger.warning(f"No document found for identifier '{identifier}'. Checking what's available...")

            # Get a few sample records for debugging
            sample_response = self.supabase.table("cleaned_documents").select("id, session_id").limit(5).execute()
            if sample_response.data:
                logger.info("Sample cleaned_documents records:")
                for record in sample_response.data:
                    logger.info(f"  ID: {record['id']}, session_id: {record['session_id']}")
            else:
                logger.warning("No records found in cleaned_documents table!")

            logger.warning(f"No cleaned document found for identifier '{identifier}'")
            return None

        except Exception as e:
            logger.error(f"Error finding document ID: {e}")
            return None

    async def _save_mcqs_to_database(self, mcqs: List[Dict], document_id: str) -> List[Dict]:
        """Save MCQs to Supabase MCQ table"""
        try:
            saved_mcqs = []

            for mcq in mcqs:
                # Prepare data for database
                mcq_data = {
                    "question": mcq.get("question", ""),
                    "correct_answer": mcq.get("correct_answer", ""),
                    "document_id": document_id  # This should be the documents.id, not cleaned_documents.id
                }

                # Handle the case where correct answer might be in different positions
                options = mcq.get("options", [])
                correct_answer = mcq.get("correct_answer", "")

                # Remove correct answer from options to get pure distractors
                distractors = [opt for opt in options if opt != correct_answer]

                # Ensure we have exactly 3 distractors
                while len(distractors) < 3:
                    distractors.append("")

                mcq_data.update({
                    "distractor1": distractors[0] if len(distractors) > 0 else "",
                    "distractor2": distractors[1] if len(distractors) > 1 else "",
                    "distractor3": distractors[2] if len(distractors) > 2 else "",
                })

                # Insert into database
                try:
                    response = self.supabase.table("mcq").insert(mcq_data).execute()

                    if response.data:
                        saved_mcq = response.data[0]
                        # Add original MCQ metadata for response
                        saved_mcq.update({
                            "difficulty": mcq.get("difficulty", "Medium"),
                            "confidence": mcq.get("confidence", 0.0),
                            "context": mcq.get("context", "")
                        })
                        saved_mcqs.append(saved_mcq)
                        logger.info(f"Saved MCQ with ID: {saved_mcq.get('id')}")
                    else:
                        logger.error(f"No data returned when inserting MCQ: {mcq_data}")

                except Exception as insert_error:
                    logger.error(f"Error inserting individual MCQ: {insert_error}")
                    logger.error(f"MCQ data that failed: {mcq_data}")
                    # Continue with other MCQs instead of failing completely
                    continue

            return saved_mcqs

        except Exception as e:
            logger.error(f"Error saving MCQs to database: {e}")
            raise

    async def generate_mcqs_from_document(self, document_identifier: str, session_id: str) -> Dict[str, Any]:
        """
        Generate MCQs from a document's cleaned text and store in database
        Enhanced with better error handling and debugging
        """
        try:
            # Update status
            self.processing_status[session_id] = {
                "status": "processing",
                "stage": "fetching_document",
                "progress": 5,
                "started_at": datetime.now().isoformat()
            }

            logger.info(f"Starting MCQ generation for document {document_identifier}, session {session_id}")

            # First, find the actual document ID from the cleaned_documents table
            actual_document_id = await self._find_document_id(document_identifier)
            if not actual_document_id:
                error_msg = f"No document found for identifier {document_identifier}"
                logger.error(error_msg)

                # Check both tables for debugging
                logger.info("Debugging: Checking both tables...")

                # Check cleaned_documents
                cleaned_check = self.supabase.table("cleaned_documents").select("id, session_id").limit(3).execute()
                logger.info(f"Sample from cleaned_documents: {cleaned_check.data}")

                # Check documents table too
                docs_check = self.supabase.table("documents").select("id, session_id").limit(3).execute()
                logger.info(f"Sample from documents: {docs_check.data}")

                raise ValueError(error_msg)

            logger.info(f"Found document ID: {actual_document_id}")

            # Fetch document text
            document_text = await self._fetch_document_text(document_identifier)
            if not document_text:
                raise ValueError(f"No cleaned text found for document {document_identifier}")

            logger.info(f"Retrieved document text: {len(document_text)} characters")

            self.processing_status[session_id]["stage"] = "generating_mcqs"
            self.processing_status[session_id]["progress"] = 20

            # Run the CPU-intensive task in a separate thread
            loop = asyncio.get_event_loop()
            mcqs = await loop.run_in_executor(
                self.executor,
                self._generate_mcqs_sync,
                document_text,
                session_id
            )

            logger.info(f"Generated {len(mcqs)} MCQs")

            self.processing_status[session_id]["stage"] = "saving_to_database"
            self.processing_status[session_id]["progress"] = 80

            # Save MCQs to database using the ACTUAL document ID
            logger.info(f"Saving MCQs with document_id: {actual_document_id}")
            saved_mcqs = await self._save_mcqs_to_database(mcqs, actual_document_id)

            # Update final status
            self.processing_status[session_id] = {
                "status": "completed",
                "stage": "finished",
                "progress": 100,
                "completed_at": datetime.now().isoformat(),
                "mcq_count": len(saved_mcqs),
                "document_id": actual_document_id
            }

            logger.info(f"MCQ generation completed for document {actual_document_id}: {len(saved_mcqs)} MCQs")

            return {
                "success": True,
                "mcqs": saved_mcqs,
                "statistics": self._generate_statistics(saved_mcqs),
                "metadata": {
                    "session_id": session_id,
                    "document_id": actual_document_id,
                    "generated_at": datetime.now().isoformat(),
                    "total_mcqs": len(saved_mcqs)
                }
            }

        except Exception as e:
            logger.error(f"MCQ generation failed for document {document_identifier}: {e}", exc_info=True)
            self.processing_status[session_id] = {
                "status": "failed",
                "stage": "error",
                "progress": 0,
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
                "document_id": document_identifier
            }
            raise

    async def _fetch_document_text(self, document_identifier: str) -> Optional[str]:
        """Fetch cleaned text from cleaned_documents table with better error handling"""
        try:
            logger.info(f"Fetching document text for identifier: {document_identifier}")

            # First try to get the document using document_identifier as session_id
            response = self.supabase.table("cleaned_documents").select("cleaned_text, id, session_id").eq("session_id",
                                                                                                          document_identifier).execute()

            if response.data:
                record = response.data[0]
                logger.info(f"Found cleaned text by session_id {document_identifier} (doc_id: {record['id']})")
                text = record["cleaned_text"]
                if text and len(text.strip()) > 0:
                    logger.info(f"Retrieved text length: {len(text)} characters")
                    return text
                else:
                    logger.warning(f"Empty cleaned_text for session_id {document_identifier}")

            # If that doesn't work, try using document_identifier as actual document ID
            response = self.supabase.table("cleaned_documents").select("cleaned_text, id, session_id").eq("id",
                                                                                                          document_identifier).execute()

            if response.data:
                record = response.data[0]
                logger.info(
                    f"Found cleaned text by document_id {document_identifier} (session_id: {record['session_id']})")
                text = record["cleaned_text"]
                if text and len(text.strip()) > 0:
                    logger.info(f"Retrieved text length: {len(text)} characters")
                    return text
                else:
                    logger.warning(f"Empty cleaned_text for document_id {document_identifier}")

            # Debug: Check if document exists but has no cleaned_text
            check_response = self.supabase.table("cleaned_documents").select("id, session_id, original_filename").or_(
                f"session_id.eq.{document_identifier},id.eq.{document_identifier}").execute()

            if check_response.data:
                record = check_response.data[0]
                logger.warning(
                    f"Document exists but no cleaned_text: ID={record['id']}, session_id={record['session_id']}, filename={record.get('original_filename', 'N/A')}")
            else:
                logger.warning(f"Document {document_identifier} not found in cleaned_documents table")

            return None

        except Exception as e:
            logger.error(f"Error fetching document text: {e}")
            return None

    def _generate_mcqs_sync(self, text: str, session_id: str) -> List[Dict]:
        """Synchronous MCQ generation (runs in thread)"""
        try:
            # Update status stages
            def update_status(stage: str, progress: int):
                if session_id in self.processing_status:
                    self.processing_status[session_id] = {
                        **self.processing_status[session_id],
                        "stage": stage,
                        "progress": progress
                    }

            update_status("processing_text", 25)

            # Generate MCQs using the updated function
            mcqs = generate_quality_mcqs_from_text(text)

            update_status("post_processing", 70)

            return mcqs

        except Exception as e:
            logger.error(f"Sync MCQ generation error: {e}")
            raise

    async def _save_mcqs_to_database(self, mcqs: List[Dict], document_id: str) -> List[Dict]:
        """Save MCQs to Supabase MCQ table with enhanced error handling"""
        try:
            logger.info(f"Attempting to save {len(mcqs)} MCQs with document_id: {document_id}")

            # First, verify the document_id exists in cleaned_documents
            verify_response = self.supabase.table("cleaned_documents").select("id, session_id").eq("id",
                                                                                                   document_id).execute()

            if not verify_response.data:
                logger.error(f"Document ID {document_id} does not exist in cleaned_documents table!")
                # Let's see what IDs are available
                sample_response = self.supabase.table("cleaned_documents").select("id, session_id").limit(5).execute()
                logger.error(f"Available document IDs: {[r['id'] for r in sample_response.data]}")
                raise ValueError(f"Document ID {document_id} not found in cleaned_documents table")
            else:
                logger.info(
                    f"Verified document ID {document_id} exists (session_id: {verify_response.data[0]['session_id']})")

            saved_mcqs = []

            for i, mcq in enumerate(mcqs):
                logger.info(f"Saving MCQ {i + 1}/{len(mcqs)}")

                # Prepare data for database
                mcq_data = {
                    "question": mcq.get("question", ""),
                    "correct_answer": mcq.get("correct_answer", ""),
                    "document_id": document_id
                }

                # Handle options and distractors
                options = mcq.get("options", [])
                correct_answer = mcq.get("correct_answer", "")

                # Remove correct answer from options to get pure distractors
                distractors = [opt for opt in options if opt != correct_answer]

                # Ensure we have exactly 3 distractors
                while len(distractors) < 3:
                    distractors.append("")

                mcq_data.update({
                    "distractor1": distractors[0] if len(distractors) > 0 else "",
                    "distractor2": distractors[1] if len(distractors) > 1 else "",
                    "distractor3": distractors[2] if len(distractors) > 2 else "",
                })

                # Log the data being inserted
                logger.debug(f"Inserting MCQ data: {mcq_data}")

                # Insert into database
                try:
                    response = self.supabase.table("mcq").insert(mcq_data).execute()

                    if response.data:
                        saved_mcq = response.data[0]
                        # Add original MCQ metadata for response
                        saved_mcq.update({
                            "difficulty": mcq.get("difficulty", "Medium"),
                            "confidence": mcq.get("confidence", 0.0),
                            "context": mcq.get("context", "")
                        })
                        saved_mcqs.append(saved_mcq)
                        logger.info(f"Successfully saved MCQ with ID: {saved_mcq.get('id')}")
                    else:
                        logger.error(f"No data returned when inserting MCQ: {mcq_data}")

                except Exception as insert_error:
                    logger.error(f"Error inserting individual MCQ {i + 1}: {insert_error}")
                    logger.error(f"MCQ data that failed: {mcq_data}")
                    # Continue with other MCQs instead of failing completely
                    continue

            logger.info(f"Successfully saved {len(saved_mcqs)} out of {len(mcqs)} MCQs")
            return saved_mcqs

        except Exception as e:
            logger.error(f"Error saving MCQs to database: {e}")
            raise

    def _generate_statistics(self, mcqs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics for the MCQs"""
        if not mcqs:
            return {
                "total_mcqs": 0,
                "average_question_length": 0,
                "average_answer_length": 0,
                "unique_topics": 0
            }

        total_mcqs = len(mcqs)

        # Calculate average lengths
        question_lengths = [len(mcq.get("question", "")) for mcq in mcqs]
        answer_lengths = [len(mcq.get("correct_answer", "")) for mcq in mcqs]

        avg_question_length = sum(question_lengths) / len(question_lengths) if question_lengths else 0
        avg_answer_length = sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0

        # Count unique question types or topics (this is a simple heuristic)
        question_words = set()
        for mcq in mcqs:
            question = mcq.get("question", "").lower()
            # Extract first few words as topic indicators
            words = question.split()[:3]
            if words:
                question_words.add(" ".join(words))

        return {
            "total_mcqs": total_mcqs,
            "average_question_length": round(avg_question_length, 2),
            "average_answer_length": round(avg_answer_length, 2),
            "unique_question_patterns": len(question_words),
            "generated_at": datetime.now().isoformat()
        }

    async def get_mcqs_by_document(self, document_id: str) -> List[Dict]:
        """Retrieve all MCQs for a specific document"""
        try:
            response = self.supabase.table("mcq").select("*").eq("document_id", document_id).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching MCQs for document {document_id}: {e}")
            return []

    async def get_mcq_by_id(self, mcq_id: str) -> Optional[Dict]:
        """Retrieve a specific MCQ by ID"""
        try:
            response = self.supabase.table("mcq").select("*").eq("id", mcq_id).single().execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching MCQ {mcq_id}: {e}")
            return None

    async def delete_mcq(self, mcq_id: str) -> bool:
        """Delete a specific MCQ"""
        try:
            response = self.supabase.table("mcq").delete().eq("id", mcq_id).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error deleting MCQ {mcq_id}: {e}")
            return False

    async def update_mcq(self, mcq_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        """Update a specific MCQ"""
        try:
            # Filter updates to only include valid columns
            valid_columns = ["question", "distractor1", "distractor2", "distractor3", "correct_answer"]
            filtered_updates = {k: v for k, v in updates.items() if k in valid_columns}

            response = self.supabase.table("mcq").update(filtered_updates).eq("id", mcq_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating MCQ {mcq_id}: {e}")
            return None

    def get_processing_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get processing status for a session"""
        return self.processing_status.get(session_id)

    def cleanup_session(self, session_id: str):
        """Clean up session data"""
        if session_id in self.processing_status:
            del self.processing_status[session_id]


# Global service instance
mcq_service = MCQGenerationService()