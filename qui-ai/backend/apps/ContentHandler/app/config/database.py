# config/database.py
"""Database configuration and connection management for Redis and Supabase"""

import os
import json
import redis
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
from dataclasses import asdict
from urllib.parse import urlparse

# Import our enhanced settings
from app.config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Configuration class for database connections using enhanced settings"""

    def __init__(self):
        self.settings = get_settings()

        # Validate configuration
        is_valid, errors = self.settings.is_valid()
        if not is_valid:
            logger.error(f"Configuration validation failed: {errors}")
            # Don't raise exception - let connection methods handle gracefully

        # Redis Configuration - FIXED VERSION
        self._setup_redis_config()

        # Supabase Configuration
        self._setup_supabase_config()

        # Cache Configuration
        self.CACHE_TTL = self.settings.CACHE_TTL
        self.PROCESSING_TTL = self.settings.CACHE_EXPIRY_HOURS * 3600  # Convert to seconds

    def _setup_redis_config(self):
        """Setup Redis configuration from various sources - FIXED VERSION"""

        # Always set default values first
        self.REDIS_DB = 0
        self.REDIS_DECODE_RESPONSES = True

        # Try Redis URL first (Redis Cloud format)
        if self.settings.REDIS_URL:
            try:
                parsed = urlparse(self.settings.REDIS_URL)
                self.REDIS_HOST = parsed.hostname
                self.REDIS_PORT = parsed.port
                self.REDIS_PASSWORD = parsed.password
                self.REDIS_USERNAME = parsed.username or "default"
                self.REDIS_SSL = parsed.scheme == "rediss"
                self.REDIS_URL = self.settings.REDIS_URL  # Store the URL
                logger.info("Using Redis URL configuration")
                return
            except Exception as e:
                logger.warning(f"Failed to parse Redis URL: {e}")

        # Fallback to individual components
        self.REDIS_HOST = self.settings.REDIS_HOST
        self.REDIS_PORT = self.settings.REDIS_PORT
        self.REDIS_PASSWORD = self.settings.REDIS_PASSWORD
        self.REDIS_USERNAME = self.settings.REDIS_USERNAME
        self.REDIS_SSL = self.settings.REDIS_TLS
        self.REDIS_URL = None  # No URL available

        logger.info(f"Using Redis individual configuration: {self.REDIS_HOST}:{self.REDIS_PORT}")

    def _setup_supabase_config(self):
        """Setup Supabase configuration"""
        self.SUPABASE_URL = self.settings.SUPABASE_URL
        self.SUPABASE_KEY = self.settings.SUPABASE_ANON_KEY
        self.SUPABASE_SERVICE_KEY = self.settings.SUPABASE_SERVICE_ROLE_KEY or self.settings.SUPABASE_ANON_KEY

        if not self.SUPABASE_URL:
            logger.error("SUPABASE_URL is required but not provided")
        if not self.SUPABASE_KEY:
            logger.error("SUPABASE_ANON_KEY is required but not provided")


class RedisManager:
    """Redis connection and operations manager with enhanced error handling"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._client = None
        self._is_connected = False
        self._connect()

    def _connect(self):
        """Establish Redis connection with better error handling - FIXED VERSION"""
        try:
            # First try direct URL connection (Redis Cloud recommended method)
            if hasattr(self.config, 'REDIS_URL') and self.config.REDIS_URL:
                try:
                    # Enhanced URL connection parameters for Redis Cloud
                    self._client = redis.from_url(
                        self.config.REDIS_URL,
                        decode_responses=self.config.REDIS_DECODE_RESPONSES,
                        socket_connect_timeout=10,
                        socket_timeout=10,
                        retry_on_timeout=True,
                        health_check_interval=30,
                        ssl_cert_reqs=None,  # Critical for Redis Cloud
                        retry_on_error=[redis.ConnectionError, redis.TimeoutError]
                    )

                    # Test connection
                    self._client.ping()
                    self._is_connected = True
                    logger.info(
                        f"Redis connection established via URL to {self.config.REDIS_HOST}:{self.config.REDIS_PORT}")
                    return

                except Exception as url_error:
                    logger.warning(f"Redis URL connection failed, trying manual config: {url_error}")

            # Fallback to manual connection parameters
            connection_params = {
                'host': self.config.REDIS_HOST,
                'port': self.config.REDIS_PORT,
                'db': self.config.REDIS_DB,
                'decode_responses': self.config.REDIS_DECODE_RESPONSES,
                'socket_connect_timeout': 10,
                'socket_timeout': 10,
                'retry_on_timeout': True,
                'health_check_interval': 30,
                'retry_on_error': [redis.ConnectionError, redis.TimeoutError]
            }

            # Add password if provided
            if self.config.REDIS_PASSWORD:
                connection_params['password'] = self.config.REDIS_PASSWORD

            # Add username if provided
            if hasattr(self.config, 'REDIS_USERNAME') and self.config.REDIS_USERNAME:
                connection_params['username'] = self.config.REDIS_USERNAME

            # SSL configuration for Redis Cloud
            if hasattr(self.config, 'REDIS_SSL') and self.config.REDIS_SSL:
                connection_params['ssl'] = True
                connection_params['ssl_cert_reqs'] = None  # Critical for Redis Cloud

            self._client = redis.Redis(**connection_params)

            # Test connection
            self._client.ping()
            self._is_connected = True
            logger.info(
                f"Redis connection established via manual config to {self.config.REDIS_HOST}:{self.config.REDIS_PORT}")

        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            self._is_connected = False
            self._client = None
        except redis.TimeoutError as e:
            logger.error(f"Redis timeout error: {e}")
            self._is_connected = False
            self._client = None
        except Exception as e:
            logger.error(f"Unexpected Redis connection error: {e}")
            self._is_connected = False
            self._client = None

    @property
    def client(self):
        """Get Redis client with connection health check"""
        if not self._is_connected or not self._client:
            logger.warning("Redis not connected, attempting to reconnect...")
            self._connect()

        if not self._client:
            return None

        try:
            self._client.ping()
            return self._client
        except Exception as e:
            logger.warning(f"Redis connection lost, reconnecting: {e}")
            self._connect()
            return self._client

    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self._is_connected and self.client is not None

    def ping(self) -> bool:
        """Ping Redis to check connection"""
        try:
            if self.client:
                self.client.ping()
                return True
            return False
        except:
            return False

    def set_processing_data(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Store processing data in Redis with TTL"""
        if not self.is_available():
            logger.warning("Redis not available, cannot store processing data")
            return False

        try:
            key = f"processing:{session_id}"
            ttl = ttl or self.config.PROCESSING_TTL

            # Serialize data
            serialized_data = json.dumps(data, default=str, ensure_ascii=False)

            # Store with TTL
            result = self.client.setex(key, ttl, serialized_data)
            logger.info(f"Stored processing data for session {session_id} with TTL {ttl}")
            return result
        except Exception as e:
            logger.error(f"Failed to store processing data for {session_id}: {e}")
            return False

    def get_processing_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve processing data from Redis"""
        if not self.is_available():
            logger.warning("Redis not available, cannot retrieve processing data")
            return None

        try:
            key = f"processing:{session_id}"
            data = self.client.get(key)

            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve processing data for {session_id}: {e}")
            return None

    def delete_processing_data(self, session_id: str) -> bool:
        """Delete processing data from Redis cache"""
        if not self.is_available():
            logger.warning("Redis not available, cannot delete processing data")
            return False

        try:
            key = f"processing:{session_id}"
            result = self.client.delete(key)
            logger.info(f"Deleted processing data for session {session_id}")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to delete processing data for {session_id}: {e}")
            return False

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get session processing status"""
        if not self.is_available():
            logger.warning("Redis not available, cannot retrieve session status")
            return {"status": "cache_unavailable", "timestamp": None}

        try:
            key = f"status:{session_id}"
            data = self.client.get(key)

            if data:
                return json.loads(data)
            return {"status": "not_found", "timestamp": None}
        except Exception as e:
            logger.error(f"Failed to get status for {session_id}: {e}")
            return {"status": "error", "timestamp": None}

    def set_session_status(self, session_id: str, status: str, metadata: Optional[Dict] = None) -> bool:
        """Set session processing status"""
        if not self.is_available():
            logger.warning("Redis not available, cannot set session status")
            return False

        try:
            key = f"status:{session_id}"
            status_data = {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            serialized_data = json.dumps(status_data, default=str)
            result = self.client.setex(key, self.config.CACHE_TTL, serialized_data)
            return result
        except Exception as e:
            logger.error(f"Failed to set status for {session_id}: {e}")
            return False

    def delete_cache(self, key: str) -> bool:
        """Delete any cache key"""
        if not self.is_available():
            logger.warning("Redis not available, cannot delete cache")
            return False

        try:
            result = self.client.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False


class SupabaseManager:
    """Supabase connection and operations manager with enhanced error handling"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._client = None
        self._service_client = None
        self._is_connected = False
        self._connect()

    def _connect(self):
        """Establish Supabase connections with better error handling"""
        try:
            if not self.config.SUPABASE_URL:
                logger.error("SUPABASE_URL is required but not provided")
                return

            if not self.config.SUPABASE_KEY:
                logger.error("SUPABASE_ANON_KEY is required but not provided")
                return

            # Regular client for most operations
            self._client = create_client(self.config.SUPABASE_URL, self.config.SUPABASE_KEY)

            # Service role client for admin operations
            self._service_client = create_client(self.config.SUPABASE_URL, self.config.SUPABASE_SERVICE_KEY)

            self._is_connected = True
            logger.info("Supabase connections established successfully")

        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            self._is_connected = False

    @property
    def client(self) -> Optional[Client]:
        """Get regular Supabase client"""
        if not self._is_connected:
            self._connect()
        return self._client

    @property
    def service_client(self) -> Optional[Client]:
        """Get service role Supabase client"""
        if not self._is_connected:
            self._connect()
        return self._service_client

    def is_available(self) -> bool:
        """Check if Supabase is available"""
        return self._is_connected and self._client is not None

    def create_document_record(self, summarized_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create document record using the normalized database structure"""
        if not self.is_available():
            logger.error("Supabase not available, cannot create document record")
            return None

        try:
            # Extract main document data
            document_data = {
                "session_id": summarized_data.get("session_id", ""),
                "pdf_path": summarized_data.get("pdf_path", ""),
                "original_cleaned_text": summarized_data.get("cleaned_text",
                                                             summarized_data.get("original_cleaned_text", "")),
                "combined_summary": summarized_data.get("combined_summary", "")
            }

            # Prepare metadata
            metadata = summarized_data.get("metadata", {})

            # Prepare summarized pages
            summarized_pages = []
            for page_data in summarized_data.get("summarized_pages", []):
                page_entry = {
                    "page_number": page_data.get("page_number", 0),
                    "original_text": page_data.get("original_text", page_data.get("text", "")),
                    "summary": page_data.get("summary", ""),
                    "key_points": page_data.get("key_points", []),
                    "relevance_score": page_data.get("relevance_score", 0.0),
                    "semantic_similarity": page_data.get("semantic_similarity", 0.0),
                    "content_overlap": page_data.get("content_overlap", 0.0),
                    "context_boost": page_data.get("context_boost", 0.0)
                }
                summarized_pages.append(page_entry)

            # Prepare summarization metadata
            sum_metadata = summarized_data.get("summarization_metadata", {})

            # Prepare summaries (if any exist as separate entities)
            summaries = []
            if summarized_data.get("summaries"):
                for summary in summarized_data.get("summaries", []):
                    summaries.append({
                        "summary_type": summary.get("type", "extractive"),
                        "summary_text": summary.get("text", ""),
                        "key_points": summary.get("key_points", []),
                        "metadata": summary.get("metadata", {})
                    })

            # Use the stored procedure to insert all related data
            result = self.service_client.rpc(
                "insert_document_analysis",
                {
                    "p_session_id": document_data["session_id"],
                    "p_pdf_path": document_data["pdf_path"],
                    "p_original_text": document_data["original_cleaned_text"],
                    "p_combined_summary": document_data["combined_summary"],
                    "p_metadata": metadata,
                    "p_summarized_pages": summarized_pages,
                    "p_summarization_metadata": sum_metadata,
                    "p_summaries": summaries if summaries else None,
                    "p_image_analysis": summarized_data.get("image_analysis")
                }
            ).execute()

            if result.data:
                document_id = result.data
                logger.info(
                    f"Document record created successfully with ID {document_id} for session {document_data['session_id']}")
                return {"id": document_id}
            else:
                logger.error(f"Failed to create document record: {result}")
                return None

        except Exception as e:
            logger.error(f"Error creating document record: {e}")
            return None

    def get_document_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document by session ID"""
        if not self.is_available():
            logger.error("Supabase not available, cannot retrieve document")
            return None

        try:
            result = self.client.table("documents").select("*").eq("session_id", session_id).execute()

            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error retrieving document for session {session_id}: {e}")
            return None

    def list_documents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List documents with pagination using the view"""
        if not self.is_available():
            logger.error("Supabase not available, cannot list documents")
            return []

        try:
            result = self.client.table("document_analysis_view").select("*").order("created_at", desc=True).range(
                offset, offset + limit - 1).execute()

            return result.data or []
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def delete_document(self, session_id: str) -> bool:
        """Delete document record (cascading will handle related tables)"""
        if not self.is_available():
            logger.error("Supabase not available, cannot delete document")
            return False

        try:
            result = self.service_client.table("documents").delete().eq("session_id", session_id).execute()

            return bool(result.data)
        except Exception as e:
            logger.error(f"Error deleting document for session {session_id}: {e}")
            return False

    def create_processing_log(self, session_id: str, operation_type: str, status: str,
                              metadata: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Create processing log entry"""
        if not self.is_available():
            logger.warning("Supabase not available, cannot create processing log")
            return None

        try:
            log_data = {
                "session_id": session_id,
                "operation_type": operation_type,
                "status": status,
                "metadata": metadata or {}
            }

            result = self.service_client.table("processing_logs").insert(log_data).execute()

            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating processing log: {e}")
            return None


# Singleton instances
_config = None
_redis_manager = None
_supabase_manager = None


def get_database_config() -> DatabaseConfig:
    """Get database configuration singleton"""
    global _config
    if _config is None:
        _config = DatabaseConfig()
    return _config


def get_redis_manager() -> RedisManager:
    """Get Redis manager singleton"""
    global _redis_manager
    if _redis_manager is None:
        config = get_database_config()
        _redis_manager = RedisManager(config)
    return _redis_manager


def get_supabase_manager() -> SupabaseManager:
    """Get Supabase manager singleton"""
    global _supabase_manager
    if _supabase_manager is None:
        config = get_database_config()
        _supabase_manager = SupabaseManager(config)
    return _supabase_manager