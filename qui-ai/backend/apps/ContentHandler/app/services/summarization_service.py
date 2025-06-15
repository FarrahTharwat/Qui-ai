# app/services/summarization_service.py
"""RAG-based document summarization service"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio
from dataclasses import asdict

from model.RAG_Summarize import EnhancedRAGSummarizer, SummarizedDocument
from app.config.database import get_supabase_manager

logger = logging.getLogger(__name__)


class SummarizationService:
    def __init__(self):
        self.summarizer: Optional[EnhancedRAGSummarizer] = None
        self.supabase = None
        self._initialize_supabase()
        self._config = {
            "embedding_model_name": "all-MiniLM-L6-v2",
            "summarization_model": "facebook/bart-large-cnn",
            "chunk_size": 512,
            "overlap_size": 100,
            "relevance_threshold": 0.3
        }

    def _initialize_supabase(self):
        """Initialize Supabase connection with error handling"""
        try:
            self.supabase = get_supabase_manager()

            # Check if supabase has the required methods
            if hasattr(self.supabase, 'table'):
                logger.info("Supabase initialized successfully with table method")
            elif hasattr(self.supabase, 'client') and hasattr(self.supabase.client, 'table'):
                # If it's wrapped, use the client
                self.supabase = self.supabase.client
                logger.info("Supabase initialized successfully with client.table method")
            else:
                logger.warning("Supabase manager doesn't have expected table method")
                self.supabase = None
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            self.supabase = None

    async def initialize(self):
        """Initialize the RAG summarizer"""
        try:
            logger.info("Initializing Enhanced RAG Summarizer...")

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.summarizer = await loop.run_in_executor(
                None,
                self._create_summarizer
            )

            logger.info("RAG Summarizer initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize RAG Summarizer: {e}")
            return False

    def _create_summarizer(self) -> EnhancedRAGSummarizer:
        """Create summarizer instance (runs in thread pool)"""
        return EnhancedRAGSummarizer(
            embedding_model_name=self._config["embedding_model_name"],
            summarization_model=self._config["summarization_model"],
            chunk_size=self._config["chunk_size"],
            overlap_size=self._config["overlap_size"],
            relevance_threshold=self._config["relevance_threshold"]
        )

    async def load_document_data(self, session_id: str, document_id: str) -> Dict[str, Any]:
        """Load document data from Supabase or file system"""

        # Try loading from Supabase first
        if self.supabase:
            try:
                logger.info(f"Loading document from Supabase: {session_id}/{document_id}")

                # Try multiple table queries to find the document
                tables_to_check = [
                    ('cleaned_documents', 'session_id', 'id'),
                    ('documents', 'session_id', 'id'),
                    ('cleaned_documents', 'session_id', 'session_id'),  # if document_id is actually session_id
                ]

                for table_name, session_col, doc_col in tables_to_check:
                    try:
                        response = (self.supabase.table(table_name)
                                    .select('*')
                                    .eq(session_col, session_id)
                                    .eq(doc_col, document_id)
                                    .execute())

                        if response.data and len(response.data) > 0:
                            document = response.data[0]
                            logger.info(f"Document loaded from Supabase table {table_name}")
                            return self._normalize_document_data(document, session_id, document_id)
                    except Exception as e:
                        logger.debug(f"Failed to query table {table_name}: {e}")
                        continue

                # Try searching by document_id only
                for table_name in ['cleaned_documents', 'documents']:
                    try:
                        response = (self.supabase.table(table_name)
                                    .select('*')
                                    .eq('id', document_id)
                                    .execute())

                        if response.data and len(response.data) > 0:
                            document = response.data[0]
                            logger.info(f"Document loaded from Supabase table {table_name} by ID only")
                            return self._normalize_document_data(document, session_id, document_id)
                    except Exception as e:
                        logger.debug(f"Failed to query table {table_name} by ID: {e}")
                        continue

                # Try searching by session_id only and find the most recent
                for table_name in ['cleaned_documents', 'documents']:
                    try:
                        response = (self.supabase.table(table_name)
                                    .select('*')
                                    .eq('session_id', session_id)
                                    .order('created_at', desc=True)
                                    .limit(1)
                                    .execute())

                        if response.data and len(response.data) > 0:
                            document = response.data[0]
                            logger.info(f"Document loaded from Supabase table {table_name} by session_id (most recent)")
                            return self._normalize_document_data(document, session_id, document_id)
                    except Exception as e:
                        logger.debug(f"Failed to query table {table_name} by session_id: {e}")
                        continue

                logger.warning(
                    f"Document not found in Supabase for session_id: {session_id}, document_id: {document_id}")

            except Exception as e:
                logger.warning(f"Failed to load from Supabase: {e}")

        # Fallback to file system
        try:
            logger.info(f"Trying file system fallback for: {session_id}/{document_id}")

            # Expanded list of possible paths
            possible_paths = [
                f"processed/{session_id}/{document_id}.json",
                f"processed/{session_id}_{document_id}.json",
                f"uploads/{session_id}/{document_id}/processed.json",
                f"data/{session_id}/{document_id}.json",
                f"documents/{session_id}/{document_id}.json",
                f"output/{session_id}/{document_id}.json",
                f"temp/{session_id}/{document_id}.json",
                f"storage/{session_id}/{document_id}.json",
                f"{session_id}/{document_id}.json",
                f"{document_id}.json",
                f"processed/{document_id}.json",
                f"uploads/{document_id}.json"
            ]

            for path in possible_paths:
                file_path = Path(path)
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        logger.info(f"Document loaded from file: {path}")
                        return self._normalize_document_data(data, session_id, document_id)
                    except Exception as e:
                        logger.warning(f"Failed to load from {path}: {e}")
                        continue

            # Try to find any JSON files in common directories
            search_dirs = ['processed', 'uploads', 'data', 'documents', 'output', 'temp', 'storage']
            for search_dir in search_dirs:
                try:
                    search_path = Path(search_dir)
                    if search_path.exists():
                        # Look for files containing the session_id or document_id
                        for json_file in search_path.rglob('*.json'):
                            if session_id in str(json_file) or document_id in str(json_file):
                                try:
                                    with open(json_file, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                    logger.info(f"Document found by name match: {json_file}")
                                    return self._normalize_document_data(data, session_id, document_id)
                                except Exception as e:
                                    logger.debug(f"Failed to load {json_file}: {e}")
                                    continue
                except Exception as e:
                    logger.debug(f"Error searching in {search_dir}: {e}")

        except Exception as e:
            logger.error(f"File system fallback failed: {e}")

        # If neither worked, raise error
        raise FileNotFoundError(f"Document not found for session_id: {session_id}, document_id: {document_id}")

    def _normalize_document_data(self, document: Dict[str, Any], session_id: str, document_id: str) -> Dict[str, Any]:
        """Normalize document data format"""
        return {
            'session_id': document.get('session_id', session_id),
            'document_id': document.get('id', document.get('document_id', document_id)),
            'polished_pages': document.get('polished_pages', []),
            'cleaned_text': document.get('cleaned_text', document.get('original_cleaned_text', '')),
            'metadata': document.get('metadata', {}),
            'pdf_path': document.get('pdf_path', ''),
            'image_analysis': document.get('image_analysis', {}),
            'original_filename': document.get('original_filename', ''),
            'created_at': document.get('created_at', datetime.now().isoformat())
        }

    def validate_document_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate document data and return validation info"""
        result = {
            "valid": False,
            "pages_count": 0,
            "has_cleaned_text": False,
            "issues": []
        }

        # Check required fields
        if 'polished_pages' not in data and 'cleaned_text' not in data:
            result["issues"].append("Missing both polished_pages and cleaned_text")
            return result

        # Check polished_pages
        polished_pages = data.get('polished_pages', [])
        if polished_pages:
            valid_pages = []
            for i, page in enumerate(polished_pages):
                if (page is not None and
                        isinstance(page, (str, dict)) and
                        len(str(page).strip()) > 10 and
                        not str(page).strip().lower().startswith('page_') and
                        not str(page).strip().lower().startswith('placeholder')):
                    valid_pages.append(page)

            result["pages_count"] = len(valid_pages)

            if len(valid_pages) == 0:
                result["issues"].append("No valid pages found in polished_pages")
            else:
                result["valid"] = True

        # Check cleaned_text as fallback
        cleaned_text = data.get('cleaned_text', '')
        if cleaned_text and len(cleaned_text.strip()) > 100:
            result["has_cleaned_text"] = True
            if not result["valid"]:  # Use as fallback
                result["valid"] = True

        return result

    async def check_document_status(self, session_id: str, document_id: str) -> Dict[str, Any]:
        """Check if document exists and can be summarized"""
        try:
            # Try to load document
            document_data = await self.load_document_data(session_id, document_id)

            # Validate document
            validation = self.validate_document_data(document_data)

            return {
                "exists": True,
                "valid": validation["valid"],
                "pages_count": validation["pages_count"],
                "has_cleaned_text": validation["has_cleaned_text"],
                "issues": validation.get("issues", [])
            }

        except FileNotFoundError:
            return {
                "exists": False,
                "valid": False,
                "pages_count": 0,
                "has_cleaned_text": False,
                "issues": ["Document not found"]
            }
        except Exception as e:
            logger.error(f"Error checking document status: {e}")
            return {
                "exists": False,
                "valid": False,
                "pages_count": 0,
                "has_cleaned_text": False,
                "issues": [f"Error checking status: {str(e)}"]
            }

    async def generate_summary(self, session_id: str, document_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate RAG-based summary for document"""

        if not self.summarizer:
            if not await self.initialize():
                raise RuntimeError("RAG Summarizer not available")

        # Load document data
        document_data = await self.load_document_data(session_id, document_id)

        # Apply configuration overrides
        if config:
            await self._apply_config_overrides(config)

        # Add metadata
        document_data['session_id'] = session_id
        document_data['document_id'] = document_id

        # Run summarization in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        summarized_doc = await loop.run_in_executor(
            None,
            self.summarizer.process_document,
            document_data
        )

        # Convert to dict format for response
        result = {
            "session_id": summarized_doc.session_id,
            "document_id": document_id,
            "combined_summary": summarized_doc.combined_summary,
            "page_summaries": [
                {
                    "page_number": page.page_number,
                    "summary": page.summary,
                    "key_points": page.key_points,
                    "relevance_score": page.relevance_score,
                    "semantic_similarity": page.semantic_similarity,
                    "content_overlap": page.content_overlap,
                    "context_boost": page.context_boost,
                    "original_text": page.original_text
                }
                for page in summarized_doc.summarized_pages
            ],
            "summarization_metadata": summarized_doc.summarization_metadata,
            "original_metadata": summarized_doc.metadata,
            "pdf_path": summarized_doc.pdf_path,
            "image_analysis": summarized_doc.image_analysis,
            "original_text_length": len(summarized_doc.original_cleaned_text),
            "timestamp": summarized_doc.timestamp
        }

        return result

    async def _apply_config_overrides(self, config: Dict[str, Any]):
        """Apply configuration overrides to summarizer"""
        if not self.summarizer:
            return

        # Apply overrides
        if 'relevance_threshold' in config:
            self.summarizer.relevance_threshold = config['relevance_threshold']
            logger.info(f"Applied relevance_threshold: {config['relevance_threshold']}")

        if 'chunk_size' in config:
            self.summarizer.chunk_size = config['chunk_size']
            logger.info(f"Applied chunk_size: {config['chunk_size']}")

        if 'overlap_size' in config:
            self.summarizer.overlap_size = config['overlap_size']
            logger.info(f"Applied overlap_size: {config['overlap_size']}")

    async def _ensure_document_exists(self, session_id: str, document_id: str) -> str:
        """Ensure document exists in the documents table and return the actual document_id"""
        if not self.supabase:
            logger.warning("Supabase not available, cannot ensure document exists")
            return document_id

        try:
            # First, check if document already exists in documents table
            response = (self.supabase.table('documents')
                        .select('id')
                        .eq('id', document_id)
                        .execute())

            if response.data and len(response.data) > 0:
                logger.info(f"Document {document_id} already exists in documents table")
                return document_id

            # If not found by ID, try to find it by session_id
            response = (self.supabase.table('documents')
                        .select('id')
                        .eq('session_id', session_id)
                        .execute())

            if response.data and len(response.data) > 0:
                existing_doc_id = response.data[0]['id']
                logger.info(f"Found existing document for session {session_id}: {existing_doc_id}")
                return existing_doc_id

            # If document doesn't exist, try to find it in cleaned_documents and create entry
            cleaned_doc_response = (self.supabase.table('cleaned_documents')
                                    .select('*')
                                    .eq('session_id', session_id)
                                    .execute())

            if cleaned_doc_response.data and len(cleaned_doc_response.data) > 0:
                cleaned_doc = cleaned_doc_response.data[0]

                # Create document entry based on cleaned_documents data
                document_data = {
                    'id': document_id,  # Use the provided document_id
                    'session_id': session_id,
                    'pdf_path': cleaned_doc.get('pdf_path', ''),
                    'original_cleaned_text': cleaned_doc.get('cleaned_text', ''),
                    'metadata': cleaned_doc.get('metadata', {}),
                    'image_analysis': cleaned_doc.get('image_analysis', {}),
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }

                # Insert into documents table
                response = (self.supabase.table('documents')
                            .insert(document_data)
                            .execute())

                if response.data:
                    logger.info(f"Created document entry for {document_id}")
                    return document_id
                else:
                    logger.warning(f"Failed to create document entry for {document_id}")

            # As a last resort, create a minimal document entry
            logger.info(f"Creating minimal document entry for {document_id}")
            minimal_document_data = {
                'id': document_id,
                'session_id': session_id,
                'pdf_path': '',
                'original_cleaned_text': '',
                'metadata': {'created_by': 'summarization_service'},
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            response = (self.supabase.table('documents')
                        .insert(minimal_document_data)
                        .execute())

            if response.data:
                logger.info(f"Created minimal document entry for {document_id}")
                return document_id
            else:
                logger.error(f"Failed to create minimal document entry for {document_id}")
                return document_id

        except Exception as e:
            logger.error(f"Error ensuring document exists: {e}")
            return document_id

    async def store_summary_result(self, session_id: str, document_id: str, summary_result: Dict[str, Any]):
        """Store summary result in database (background task)"""
        try:
            logger.info(f"Storing summary result for {session_id}/{document_id}")

            if not self.supabase:
                logger.warning("Supabase not available, skipping summary storage")
                return

            # Ensure the document exists in the documents table
            actual_document_id = await self._ensure_document_exists(session_id, document_id)

            # Prepare data for storage in the 'summaries' table
            summary_data = {
                'document_id': actual_document_id,
                'summary_type': 'rag_enhanced',
                'summary_text': summary_result['combined_summary'],
                'key_points': [
                    point for page in summary_result.get('page_summaries', [])
                    for point in page.get('key_points', [])
                ],
                'metadata': {
                    'session_id': session_id,
                    'summarization_metadata': summary_result.get('summarization_metadata', {}),
                    'page_summaries_count': len(summary_result.get('page_summaries', [])),
                    'processing_info': {
                        'timestamp': summary_result.get('timestamp', datetime.now().isoformat()),
                        'original_text_length': summary_result.get('original_text_length', 0)
                    }
                }
            }

            # Store in Supabase summaries table
            response = self.supabase.table('summaries').upsert(summary_data).execute()

            if response.data:
                logger.info(f"Summary stored successfully in summaries table for {actual_document_id}")

                # Also store detailed page summaries if needed
                await self._store_page_summaries(actual_document_id, summary_result.get('page_summaries', []))
            else:
                logger.warning(f"Failed to store summary for {actual_document_id}")

        except Exception as e:
            logger.error(f"Error storing summary result: {e}")

    async def _store_page_summaries(self, document_id: str, page_summaries: List[Dict[str, Any]]):
        """Store detailed page summaries in summarized_pages table"""
        try:
            if not self.supabase or not page_summaries:
                return

            # Prepare page summaries data
            page_data = []
            for page in page_summaries:
                page_data.append({
                    'document_id': document_id,
                    'page_number': page.get('page_number', 0),
                    'original_text': page.get('original_text', ''),
                    'summary': page.get('summary', ''),
                    'key_points': page.get('key_points', []),
                    'relevance_score': page.get('relevance_score', 0.0),
                    'semantic_similarity': page.get('semantic_similarity', 0.0),
                    'content_overlap': page.get('content_overlap', 0.0),
                    'context_boost': page.get('context_boost', 0.0)
                })

            # Store page summaries
            response = self.supabase.table('summarized_pages').upsert(page_data).execute()

            if response.data:
                logger.info(f"Stored {len(page_data)} page summaries for document {document_id}")
            else:
                logger.warning(f"Failed to store page summaries for {document_id}")

        except Exception as e:
            logger.error(f"Error storing page summaries: {e}")

    async def get_existing_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get existing summary for document"""
        try:
            if not self.supabase:
                return None

            response = self.supabase.table('summaries').select('*').eq('document_id', document_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Error fetching existing summary: {e}")
            return None

    async def delete_summary(self, document_id: str) -> bool:
        """Delete summary for document"""
        try:
            if not self.supabase:
                return False

            # Delete from summaries table
            response = self.supabase.table('summaries').delete().eq('document_id', document_id).execute()

            # Also delete from summarized_pages table
            try:
                self.supabase.table('summarized_pages').delete().eq('document_id', document_id).execute()
            except Exception as e:
                logger.warning(f"Error deleting page summaries: {e}")

            return response.data is not None and len(response.data) > 0

        except Exception as e:
            logger.error(f"Error deleting summary: {e}")
            return False

    async def get_summarization_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get summarization history for session"""
        try:
            if not self.supabase:
                return []

            # Query summaries table and filter by session_id in metadata
            response = (
                self.supabase.table('summaries')
                .select('document_id, created_at, metadata, summary_type')
                .order('created_at', desc=True)
                .limit(limit * 2)  # Get more to filter
                .execute()
            )

            # Filter by session_id in metadata
            filtered_results = []
            for item in response.data or []:
                metadata = item.get('metadata', {})
                if metadata.get('session_id') == session_id:
                    filtered_results.append(item)
                    if len(filtered_results) >= limit:
                        break

            return filtered_results

        except Exception as e:
            logger.error(f"Error fetching summarization history: {e}")
            return []

    async def get_current_config(self) -> Dict[str, Any]:
        """Get current summarization configuration"""
        return self._config.copy()

    async def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update summarization configuration"""
        # Validate and update config
        valid_keys = {
            'embedding_model_name', 'summarization_model',
            'chunk_size', 'overlap_size', 'relevance_threshold'
        }

        for key, value in new_config.items():
            if key in valid_keys:
                self._config[key] = value
                logger.info(f"Updated config {key}: {value}")

        # Reinitialize summarizer with new config if needed
        model_keys = {'embedding_model_name', 'summarization_model'}
        if any(key in new_config for key in model_keys):
            logger.info("Model config changed, reinitializing summarizer...")
            await self.initialize()

        return self._config.copy()

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self.summarizer is not None


# Global service instance
summarization_service = SummarizationService()