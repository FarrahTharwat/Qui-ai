# config/database.py
"""Database configuration and connection management for Redis and Supabase"""

import os
import json
import redis
from supabase import create_client, Client
from typing import Optional, Dict, Any, List, Union
import logging
from datetime import datetime
from urllib.parse import urlparse

# Import our enhanced settings
from app.config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Configuration class for database connections using enhanced settings"""

    def __init__(self):
        self.settings = get_settings()
        self.CACHE_TTL = self.settings.CACHE_TTL
        self.PROCESSING_TTL = self.settings.CACHE_EXPIRY_HOURS * 3600
        self._setup_redis_config()
        self._setup_supabase_config()

    def _setup_redis_config(self):
        """Setup Redis configuration from various sources"""
        # Default values
        self.REDIS_DB = 0
        self.REDIS_DECODE_RESPONSES = True
        self.REDIS_SSL = False
        self.REDIS_URL = None

        # Try to parse Redis URL first
        if self.settings.REDIS_URL:
            if self._parse_redis_url():
                return

        # Fallback to individual settings
        self.REDIS_HOST = self.settings.REDIS_HOST or "localhost"
        self.REDIS_PORT = self.settings.REDIS_PORT or 6379
        self.REDIS_PASSWORD = self.settings.REDIS_PASSWORD
        self.REDIS_USERNAME = self.settings.REDIS_USERNAME or "default"
        self.REDIS_SSL = self.settings.REDIS_TLS or False

    def _parse_redis_url(self) -> bool:
        """Parse Redis URL and return True if successful"""
        try:
            parsed = urlparse(self.settings.REDIS_URL)
            self.REDIS_HOST = parsed.hostname or "localhost"
            self.REDIS_PORT = parsed.port or 6379
            self.REDIS_PASSWORD = parsed.password
            self.REDIS_USERNAME = parsed.username or "default"
            self.REDIS_SSL = parsed.scheme == "rediss"
            self.REDIS_URL = self.settings.REDIS_URL
            return True
        except Exception as e:
            logger.warning(f"Failed to parse Redis URL: {e}")
            return False

    def _setup_supabase_config(self):
        """Setup Supabase configuration"""
        self.SUPABASE_URL = self.settings.SUPABASE_URL
        self.SUPABASE_KEY = self.settings.SUPABASE_ANON_KEY
        self.SUPABASE_SERVICE_KEY = self.settings.SUPABASE_SERVICE_ROLE_KEY or self.settings.SUPABASE_ANON_KEY


class RedisManager:
    """Redis connection and operations manager"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._client = None
        self._connect()

    def _connect(self):
        """Establish Redis connection"""
        try:
            if self.config.REDIS_URL:
                self._client = redis.from_url(
                    self.config.REDIS_URL,
                    decode_responses=self.config.REDIS_DECODE_RESPONSES,
                    socket_connect_timeout=10
                )
            else:
                self._client = self._create_redis_client()

            self._client.ping()
            logger.info(f"Redis connected to {self.config.REDIS_HOST}:{self.config.REDIS_PORT}")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._client = None

    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client from individual parameters"""
        params = {
            'host': self.config.REDIS_HOST,
            'port': self.config.REDIS_PORT,
            'db': self.config.REDIS_DB,
            'decode_responses': self.config.REDIS_DECODE_RESPONSES,
            'socket_connect_timeout': 10
        }

        if self.config.REDIS_PASSWORD:
            params['password'] = self.config.REDIS_PASSWORD
        if self.config.REDIS_USERNAME != "default":
            params['username'] = self.config.REDIS_USERNAME
        if self.config.REDIS_SSL:
            params['ssl'] = True

        return redis.Redis(**params)

    @property
    def client(self):
        """Get Redis client with health check"""
        if not self._client:
            self._connect()
        return self._client

    def is_available(self) -> bool:
        """Check if Redis is available"""
        try:
            return self.client and self.client.ping()
        except:
            return False

    def _get_key(self, prefix: str, session_id: str) -> str:
        """Generate Redis key with prefix"""
        return f"{prefix}:{session_id}"

    def _safe_operation(self, operation, *args, **kwargs):
        """Safely execute Redis operation with error handling"""
        if not self.is_available():
            return None
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            return None

    def set_processing_data(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Store processing data in Redis with TTL"""
        key = self._get_key("processing", session_id)
        ttl = ttl or self.config.PROCESSING_TTL
        serialized_data = json.dumps(data, default=str)

        result = self._safe_operation(self.client.setex, key, ttl, serialized_data)
        if result is None:
            logger.error(f"Failed to store processing data for {session_id}")
            return False
        return bool(result)

    def get_processing_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve processing data from Redis"""
        key = self._get_key("processing", session_id)
        data = self._safe_operation(self.client.get, key)

        if data is None:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse processing data for {session_id}: {e}")
            return None

    def delete_processing_data(self, session_id: str) -> bool:
        """Delete processing data from Redis cache"""
        key = self._get_key("processing", session_id)
        result = self._safe_operation(self.client.delete, key)

        if result is None:
            logger.error(f"Failed to delete processing data for {session_id}")
            return False
        return bool(result)

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get session processing status"""
        timestamp = datetime.now().isoformat()

        if not self.is_available():
            return {"status": "cache_unavailable", "timestamp": timestamp}

        key = self._get_key("status", session_id)
        data = self._safe_operation(self.client.get, key)

        if data is None:
            return {"status": "not_found", "timestamp": timestamp}

        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse status for {session_id}: {e}")
            return {"status": "error", "timestamp": timestamp}

    def set_session_status(self, session_id: str, status: str, metadata: Optional[Dict] = None) -> bool:
        """Set session processing status"""
        key = self._get_key("status", session_id)
        status_data = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        serialized_data = json.dumps(status_data, default=str)

        result = self._safe_operation(self.client.setex, key, self.config.CACHE_TTL, serialized_data)
        if result is None:
            logger.error(f"Failed to set status for {session_id}")
            return False
        return bool(result)

    def delete_cache(self, key: str) -> bool:
        """Delete any cache key"""
        result = self._safe_operation(self.client.delete, key)
        if result is None:
            logger.error(f"Failed to delete cache key {key}")
            return False
        return bool(result)

    # Add this method to your RedisManager class in database.py

    def cache_processing_result(self, session_id: str, result_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache processing result data in Redis with TTL"""
        key = self._get_key("result", session_id)
        ttl = ttl or self.config.CACHE_TTL
        serialized_data = json.dumps(result_data, default=str)

        result = self._safe_operation(self.client.setex, key, ttl, serialized_data)
        if result is None:
            logger.error(f"Failed to cache processing result for {session_id}")
            return False
        return bool(result)

    def get_processing_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached processing result from Redis"""
        key = self._get_key("result", session_id)
        data = self._safe_operation(self.client.get, key)

        if data is None:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse processing result for {session_id}: {e}")
            return None

    def delete_processing_result(self, session_id: str) -> bool:
        """Delete cached processing result from Redis"""
        key = self._get_key("result", session_id)
        result = self._safe_operation(self.client.delete, key)

        if result is None:
            logger.error(f"Failed to delete processing result for {session_id}")
            return False
        return bool(result)

class SupabaseManager:
    """Supabase connection and operations manager"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._client = None
        self._service_client = None
        self._connect()

    def _connect(self):
        """Establish Supabase connections"""
        if not self.config.SUPABASE_URL or not self.config.SUPABASE_KEY:
            logger.error("Supabase URL and key are required")
            return

        try:
            self._client = create_client(self.config.SUPABASE_URL, self.config.SUPABASE_KEY)
            self._service_client = create_client(self.config.SUPABASE_URL, self.config.SUPABASE_SERVICE_KEY)
            logger.info("Supabase connections established")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")

    @property
    def client(self) -> Optional[Client]:
        """Get regular Supabase client"""
        return self._client

    @property
    def service_client(self) -> Optional[Client]:
        """Get service role Supabase client"""
        return self._service_client

    def is_available(self) -> bool:
        """Check if Supabase is available"""
        return self._client is not None

    def _ensure_array(self, value: Any, field_name: str) -> List[Any]:
        """Ensure a value is formatted as a proper JSON array"""
        if value is None:
            logger.debug(f"Field {field_name} is None, returning empty array")
            return []

        if isinstance(value, list):
            logger.debug(f"Field {field_name} is already a list with {len(value)} items")
            return value

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    logger.debug(f"Field {field_name} parsed from JSON string to list with {len(parsed)} items")
                    return parsed
                else:
                    logger.warning(f"Field {field_name} parsed from JSON but is not a list: {type(parsed)}")
                    return [parsed]
            except json.JSONDecodeError:
                logger.warning(f"Field {field_name} is string but not valid JSON, wrapping in array")
                return [value]

        if isinstance(value, dict):
            logger.debug(f"Field {field_name} is dict, wrapping in array")
            return [value]

        try:
            result = list(value) if hasattr(value, '__iter__') else [value]
            logger.debug(f"Field {field_name} converted to list: {len(result)} items")
            return result
        except:
            logger.warning(f"Field {field_name} could not be converted to array, using empty array")
            return []

    def _ensure_object(self, value: Any, field_name: str) -> Dict[str, Any]:
        """Ensure a value is formatted as a proper JSON object"""
        if value is None:
            logger.debug(f"Field {field_name} is None, returning empty object")
            return {}

        if isinstance(value, dict):
            logger.debug(f"Field {field_name} is already a dict")
            return value

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    logger.debug(f"Field {field_name} parsed from JSON string to dict")
                    return parsed
                else:
                    logger.warning(f"Field {field_name} parsed from JSON but is not a dict: {type(parsed)}")
                    return {"value": parsed}
            except json.JSONDecodeError:
                logger.warning(f"Field {field_name} is string but not valid JSON, wrapping in object")
                return {"value": value}

        logger.debug(f"Field {field_name} wrapped in object")
        return {"value": value}

    def _parse_input_data(self, summarized_data: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse and validate input data"""
        logger.info(f"Received summarized_data type: {type(summarized_data)}")

        if isinstance(summarized_data, str):
            logger.info(f"String data preview (first 200 chars): {summarized_data[:200]}...")
            try:
                data = json.loads(summarized_data)
                logger.info(f"Successfully parsed JSON string to: {type(data)}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON string: {e}")
                return None
        elif isinstance(summarized_data, dict):
            data = summarized_data
            logger.info("Using dict data directly")
        else:
            logger.error(f"Invalid data type: {type(summarized_data)}")
            return None

        if not isinstance(data, dict):
            logger.error(f"Data is not a dictionary after parsing: {type(data)}")
            return None

        session_id = data.get('session_id')
        if not session_id:
            logger.error("session_id is required but not provided")
            return None

        return data

    def _prepare_rpc_params(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare RPC parameters with validated data types"""
        # Validate and format array/object fields
        summarized_pages = self._ensure_array(data.get("summarized_pages"), "summarized_pages")
        metadata = self._ensure_object(data.get("metadata"), "metadata")
        summarization_metadata = self._ensure_object(data.get("summarization_metadata"), "summarization_metadata")
        summaries = self._ensure_object(data.get("summaries"), "summaries") if data.get("summaries") is not None else None
        image_analysis = self._ensure_object(data.get("image_analysis"), "image_analysis") if data.get("image_analysis") is not None else None

        logger.info(f"Processed summarized_pages: {len(summarized_pages)} items")

        # Prepare RPC parameters
        session_id = data.get("session_id")
        if session_id is None:
            raise ValueError("session_id is required")

        rpc_params = {
            "p_session_id": str(session_id),
            "p_pdf_path": str(data.get("pdf_path", "")),
            "p_original_text": str(data.get("original_cleaned_text", "")),
            "p_combined_summary": str(data.get("combined_summary", "")),
            "p_metadata": metadata,
            "p_summarized_pages": summarized_pages,
            "p_summarization_metadata": summarization_metadata,
            "p_summaries": summaries,
            "p_image_analysis": image_analysis
        }

        # Log parameter details for debugging
        logger.info(f"RPC parameters prepared for session {str(session_id)}:")
        for key, value in rpc_params.items():
            if key == "p_summarized_pages":
                logger.info(f"  {key}: {type(value)} with {len(value) if isinstance(value, list) else 'N/A'} items")
            elif key in ["p_metadata", "p_summarization_metadata", "p_summaries", "p_image_analysis"]:
                logger.info(f"  {key}: {type(value)} {'object' if isinstance(value, dict) else 'other'}")
            else:
                logger.info(f"  {key}: {type(value)} (length: {len(str(value)) if value else 0})")

        return rpc_params

    def _handle_api_error(self, error: Exception, session_id: str) -> None:
        """Handle API errors with comprehensive error parsing"""
        error_message = "Unknown error"
        error_code = "unknown"
        error_details = None
        error_hint = None

        try:
            # Handle different types of error objects
            if hasattr(error, 'message'):
                error_obj = error.message

                if isinstance(error_obj, str):
                    error_message = error_obj
                elif isinstance(error_obj, dict):
                    error_message = error_obj.get('message', str(error_obj))
                    error_code = error_obj.get('code', 'unknown')
                    error_details = error_obj.get('details')
                    error_hint = error_obj.get('hint')
                else:
                    error_message = str(error_obj)

            elif hasattr(error, 'args') and error.args:
                error_arg = error.args[0]

                if isinstance(error_arg, str):
                    try:
                        parsed_error = json.loads(error_arg)
                        if isinstance(parsed_error, dict):
                            error_message = parsed_error.get('message', error_arg)
                            error_code = parsed_error.get('code', 'unknown')
                            error_details = parsed_error.get('details')
                            error_hint = parsed_error.get('hint')
                        else:
                            error_message = error_arg
                    except json.JSONDecodeError:
                        error_message = error_arg
                elif isinstance(error_arg, dict):
                    error_message = error_arg.get('message', str(error_arg))
                    error_code = error_arg.get('code', 'unknown')
                    error_details = error_arg.get('details')
                    error_hint = error_arg.get('hint')
                else:
                    error_message = str(error_arg)
            else:
                error_message = str(error)

            # Log error details
            logger.error(f"API Error for session {session_id}:")
            logger.error(f"  Code: {error_code}")
            logger.error(f"  Message: {error_message}")
            if error_details:
                logger.error(f"  Details: {error_details}")
            if error_hint:
                logger.error(f"  Hint: {error_hint}")

            # Log specific error patterns
            self._log_specific_error_patterns(error_message, session_id)

        except Exception as log_error:
            logger.error(f"Error while processing API exception for session {session_id}: {log_error}")
            logger.error(f"Original exception: {repr(error)}")

    def _log_specific_error_patterns(self, error_message: str, session_id: str) -> None:
        """Log specific error patterns with detailed guidance"""
        error_lower = error_message.lower()

        error_patterns = {
            "function" in error_lower and "does not exist" in error_lower: (
                "🔴 RPC function 'insert_document_analysis' does not exist in database",
                "💡 Solution: Ensure the database function is properly created and deployed",
                "📋 Check: Run 'SELECT * FROM pg_proc WHERE proname = 'insert_document_analysis';' in SQL editor"
            ),
            "permission denied" in error_lower: (
                "🔴 Permission denied - check service role key permissions",
                "💡 Solution: Verify service role key has execute permissions on RPC functions",
                "📋 Check: Ensure service role key is correctly configured in settings"
            ),
            "could not choose the best candidate function" in error_lower: (
                "🔴 Function overloading conflict - multiple functions with similar signatures exist",
                "💡 Solution: Drop conflicting functions and recreate with unique signatures",
                "📋 Check: Look for duplicate function definitions in your database"
            ),
            "constraint" in error_lower or "violates" in error_lower: (
                "🔴 Database constraint violation",
                "💡 Solution: Check for duplicate keys, foreign key violations, or null constraints",
                "📋 Check: Review your database constraints and input data"
            ),
            "type" in error_lower and "mismatch" in error_lower: (
                "🔴 Data type mismatch",
                "💡 Solution: Ensure data types match database schema expectations",
                "📋 Check: Verify parameter types in RPC function call"
            )
        }

        for condition, (error_msg, solution, check) in error_patterns.items():
            if condition:
                logger.error(error_msg)
                logger.error(solution)
                logger.error(check)
                break

    def create_document_record(self, summarized_data: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Create document record using the normalized database structure"""
        if not self.is_available():
            logger.error("Supabase not available")
            return None

        session_id = None

        try:
            # Parse and validate input data
            data = self._parse_input_data(summarized_data)
            if not data:
                return None

            session_id = data.get("session_id")
            logger.info(f"Processing document record for session {session_id}")

            # Prepare RPC parameters
            rpc_params = self._prepare_rpc_params(data)

            # Call RPC function
            logger.info(f"Calling RPC insert_document_analysis for session {session_id}")
            result = self.service_client.rpc("insert_document_analysis", rpc_params).execute()

            # Handle the response
            document_id = None
            if hasattr(result, 'data') and result.data is not None:
                if isinstance(result.data, str):
                    document_id = result.data
                elif isinstance(result.data, list) and len(result.data) > 0:
                    document_id = str(result.data[0])
                else:
                    document_id = str(result.data)

                logger.info(f"RPC returned document_id: {document_id} (type: {type(result.data)})")

            if document_id and document_id.lower() not in ['none', 'null', '']:
                logger.info(f"✅ Document record created successfully with ID: {document_id}")
                return {"id": document_id}
            else:
                logger.error("❌ Failed to create document record - no valid ID returned")
                logger.error(f"Raw result data: {result.data if hasattr(result, 'data') else 'No data'}")
                return None

        except Exception as e:
            logger.error(f"❌ Exception in create_document_record for session {session_id or 'unknown'}")
            self._handle_api_error(e, session_id or 'unknown')

            # Log full traceback for debugging
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return None

    def get_document_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document by session ID"""
        if not self.is_available():
            return None

        try:
            result = self.client.table("documents").select("*").eq("session_id", session_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error retrieving document for session {session_id}: {e}")
            self._handle_api_error(e, session_id)
            return None

    def list_documents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List documents with pagination"""
        if not self.is_available():
            return []

        try:
            result = (self.client.table("document_analysis_view")
                      .select("*")
                      .order("created_at", desc=True)
                      .range(offset, offset + limit - 1)
                      .execute())
            return result.data or []
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            self._handle_api_error(e, "list_documents")
            return []

    def delete_document(self, session_id: str) -> bool:
        """Delete document record"""
        if not self.is_available():
            return False

        try:
            result = self.service_client.table("documents").delete().eq("session_id", session_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error deleting document for session {session_id}: {e}")
            self._handle_api_error(e, session_id)
            return False

    def create_processing_log(self, session_id: str, operation_type: str, status: str,
                              metadata: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Create processing log entry"""
        if not self.is_available():
            return None

        try:
            log_data = {
                "session_id": session_id,
                "operation_type": operation_type,
                "status": status,
                "metadata": metadata or {}
            }
            result = self.service_client.table("processing_logs").insert(log_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating processing log: {e}")
            self._handle_api_error(e, session_id)
            return None

    # Add this method to your SupabaseManager class

    def create_cleaned_document_record(self, document_data: dict) -> dict:
        """Create a record in the cleaned_documents table"""
        try:
            logger.info(f"Creating cleaned document record for session: {document_data.get('session_id')}")
            logger.info(f"Target table: cleaned_documents")
            logger.info(f"Data keys: {list(document_data.keys())}")

            # Validate required fields for cleaned_documents table
            required_fields = ['session_id', 'original_filename', 'pdf_path', 'cleaned_text']
            for field in required_fields:
                if not document_data.get(field):
                    raise ValueError(f"Required field '{field}' is missing or empty")

            # Log the text length for verification
            cleaned_text_length = len(document_data.get('cleaned_text', ''))
            logger.info(f"Cleaned text length: {cleaned_text_length}")

            # Insert into cleaned_documents table
            result = self.client.table('cleaned_documents').insert(document_data).execute()

            if result.data and len(result.data) > 0:
                document_id = result.data[0]['id']
                logger.info(f"✅ Cleaned document record created successfully with ID: {document_id}")
                logger.info(f"Saved to table: cleaned_documents")
                return result.data[0]
            else:
                logger.error(f"❌ Failed to create cleaned document record")
                logger.error(f"Supabase response: {result}")
                raise ValueError("No data returned from database insert")

        except Exception as e:
            logger.error(f"❌ Error creating cleaned document record: {e}")
            logger.error(f"Document data keys: {list(document_data.keys())}")
            logger.error(f"Session ID: {document_data.get('session_id', 'MISSING')}")

            # Log a sample of the data for debugging (without exposing sensitive info)
            sample_data = {
                'session_id': document_data.get('session_id'),
                'original_filename': document_data.get('original_filename'),
                'cleaned_text_length': len(document_data.get('cleaned_text', '')),
                'has_polished_text': bool(document_data.get('polished_text')),
                'processing_status': document_data.get('processing_status')
            }
            logger.error(f"Sample data: {sample_data}")
            raise


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
        _redis_manager = RedisManager(get_database_config())
    return _redis_manager


def get_supabase_manager() -> SupabaseManager:
    """Get Supabase manager singleton"""
    global _supabase_manager
    if _supabase_manager is None:
        _supabase_manager = SupabaseManager(get_database_config())
    return _supabase_manager