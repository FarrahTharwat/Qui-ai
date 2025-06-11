# app/services/mcq_service.py
"""MCQ Generation Service using T5 + RoBERTa models with Supabase integration"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from supabase import create_client, Client
import os

# Import the MCQ generator functions
from app.core.mcq_generator import (
    generate_quality_mcqs_from_text,
    display_mcqs_enhanced
)

logger = logging.getLogger(__name__)

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
        
    async def generate_mcqs_from_document(
        self, 
        document_id: str, 
        session_id: str
    ) -> Dict[str, Any]:
        """
        Generate MCQs from a document's cleaned text and store in database
        
        Args:
            document_id: ID of the document in the documents table
            session_id: Session identifier for tracking
            
        Returns:
            Dictionary containing results and metadata
        """
        try:
            # Update status
            self.processing_status[session_id] = {
                "status": "processing",
                "stage": "fetching_document",
                "progress": 5,
                "started_at": datetime.now().isoformat()
            }
            
            logger.info(f"Starting MCQ generation for document {document_id}, session {session_id}")
            
            # Fetch document text from Supabase
            document_text = await self._fetch_document_text(document_id)
            if not document_text:
                raise ValueError(f"No cleaned text found for document {document_id}")
            
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
            
            self.processing_status[session_id]["stage"] = "saving_to_database"
            self.processing_status[session_id]["progress"] = 80
            
            # Save MCQs to database
            saved_mcqs = await self._save_mcqs_to_database(mcqs, document_id)
            
            # Update final status
            self.processing_status[session_id] = {
                "status": "completed",
                "stage": "finished",
                "progress": 100,
                "completed_at": datetime.now().isoformat(),
                "mcq_count": len(saved_mcqs),
                "document_id": document_id
            }
            
            logger.info(f"MCQ generation completed for document {document_id}: {len(saved_mcqs)} MCQs")
            
            return {
                "success": True,
                "mcqs": saved_mcqs,
                "statistics": self._generate_statistics(saved_mcqs),
                "metadata": {
                    "session_id": session_id,
                    "document_id": document_id,
                    "generated_at": datetime.now().isoformat(),
                    "total_mcqs": len(saved_mcqs)
                }
            }
            
        except Exception as e:
            logger.error(f"MCQ generation failed for document {document_id}: {e}", exc_info=True)
            self.processing_status[session_id] = {
                "status": "failed",
                "stage": "error",
                "progress": 0,
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
                "document_id": document_id
            }
            raise
    
    async def _fetch_document_text(self, document_id: str) -> Optional[str]:
        """Fetch cleaned text from documents table"""
        try:
            response = self.supabase.table("documents").select("original_cleaned_text").eq("id", document_id).single().execute()
            
            if response.data and response.data.get("original_cleaned_text"):
                return response.data["original_cleaned_text"]
            else:
                logger.warning(f"No cleaned text found for document {document_id}")
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
        """Save MCQs to Supabase MCQ table"""
        try:
            saved_mcqs = []
            
            for mcq in mcqs:
                # Prepare data for database
                mcq_data = {
                    "question": mcq.get("question", ""),
                    "distractor1": mcq.get("options", ["", "", "", ""])[1] if len(mcq.get("options", [])) > 1 else "",
                    "distractor2": mcq.get("options", ["", "", "", ""])[2] if len(mcq.get("options", [])) > 2 else "",
                    "distractor3": mcq.get("options", ["", "", "", ""])[3] if len(mcq.get("options", [])) > 3 else "",
                    "correct_answer": mcq.get("correct_answer", ""),
                    "document_id": document_id  # Link to source document
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
                
            return saved_mcqs
            
        except Exception as e:
            logger.error(f"Error saving MCQs to database: {e}")
            raise
    
    def _generate_statistics(self, mcqs: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive statistics"""
        if not mcqs:
            return {}
        
        # Extract difficulty and confidence from MCQs if available
        difficulties = [mcq.get("difficulty", "Medium") for mcq in mcqs]
        confidences = [mcq.get("confidence", 0.0) for mcq in mcqs if mcq.get("confidence")]
        
        return {
            "total_questions": len(mcqs),
            "difficulty_distribution": {
                "easy": difficulties.count("Easy"),
                "medium": difficulties.count("Medium"),
                "hard": difficulties.count("Hard")
            },
            "confidence_stats": {
                "average": sum(confidences) / len(confidences) if confidences else 0,
                "min": min(confidences) if confidences else 0,
                "max": max(confidences) if confidences else 0,
                "high_confidence": len([c for c in confidences if c > 0.7]),
                "medium_confidence": len([c for c in confidences if 0.4 <= c <= 0.7]),
                "low_confidence": len([c for c in confidences if c < 0.4])
            },
            "question_stats": {
                "avg_question_length": sum(len(mcq.get("question", "").split()) for mcq in mcqs) / len(mcqs),
                "questions_with_all_distractors": sum(1 for mcq in mcqs 
                                                    if all([mcq.get("distractor1"), 
                                                           mcq.get("distractor2"), 
                                                           mcq.get("distractor3")]))
            }
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