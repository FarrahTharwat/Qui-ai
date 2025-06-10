# config/settings.py
"""
Enhanced environment configuration with better error handling and validation
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import logging
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)


class EnvironmentConfig:
    """Enhanced environment configuration with validation and defaults"""

    def __init__(self, env_file: Optional[str] = None):
        """Initialize configuration with optional custom .env file"""
        self._load_environment(env_file)
        self._validate_required_vars()

    def _load_environment(self, env_file: Optional[str] = None):
        """Load environment variables from .env file and system environment"""

        # Try to load from various .env file locations
        env_files_to_try = []

        if env_file:
            env_files_to_try.append(env_file)

        # Standard locations to check for .env file (more comprehensive search)
        possible_locations = [
            Path.cwd() / ".env",
            Path.cwd() / "config" / ".env",
            Path(__file__).parent / ".env",
            Path(__file__).parent.parent / ".env",
            Path(__file__).parent.parent.parent / ".env",  # For deeper nesting
            Path("/app/.env"),  # Docker container
            Path("/etc/app/.env"),  # System-wide config
        ]

        env_files_to_try.extend(possible_locations)

        # Try to load from each location
        env_loaded = False
        loaded_from = None

        for env_path in env_files_to_try:
            if isinstance(env_path, str):
                env_path = Path(env_path)

            if env_path.exists() and env_path.is_file():
                try:
                    logger.info(f"Attempting to load environment from: {env_path}")
                    load_dotenv(env_path, override=True)

                    # Verify that key variables were actually loaded
                    if os.getenv("SUPABASE_URL") or os.getenv("REDIS_URL"):
                        env_loaded = True
                        loaded_from = str(env_path)
                        logger.info(f"Successfully loaded environment from: {env_path}")
                        break
                    else:
                        logger.warning(f"Environment file found but no key variables loaded from: {env_path}")
                except Exception as e:
                    logger.warning(f"Failed to load environment from {env_path}: {e}")

        if not env_loaded:
            logger.warning("No .env file found or loaded successfully. Using system environment variables only.")
            # Still try to load from current directory as fallback
            load_dotenv(override=False)

            # Check if we have the required variables from system environment
            if os.getenv("SUPABASE_URL"):
                logger.info("Found required variables in system environment")
                env_loaded = True
                loaded_from = "system environment"

        # Log the final state
        if env_loaded and loaded_from:
            logger.info(f"Environment configuration loaded from: {loaded_from}")
        else:
            logger.error("No environment configuration could be loaded!")

    def _validate_required_vars(self):
        """Validate required environment variables"""
        required_vars = [
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY"
        ]

        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                logger.debug(f"Found {var}: {value[:20]}..." if len(value) > 20 else f"Found {var}: {value}")

        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            logger.error("Please ensure your .env file contains all required variables")
            logger.error("Available environment variables:")
            for key, value in os.environ.items():
                if any(term in key.upper() for term in ['SUPABASE', 'REDIS', 'DATABASE']):
                    masked_value = value[:10] + "..." if len(value) > 10 else value
                    logger.error(f"  {key}={masked_value}")

    # Application Settings
    @property
    def ENVIRONMENT(self) -> str:
        return os.getenv("ENVIRONMENT", "development")

    @property
    def DEBUG(self) -> bool:
        return os.getenv("DEBUG", "false").lower() == "true"

    @property
    def APP_NAME(self) -> str:
        return os.getenv("APP_NAME", "Document Processing API")

    @property
    def API_HOST(self) -> str:
        return os.getenv("API_HOST", "0.0.0.0")

    @property
    def API_PORT(self) -> int:
        return int(os.getenv("API_PORT", os.getenv("PORT", "8000")))

    # Database Configuration
    @property
    def SUPABASE_URL(self) -> Optional[str]:
        url = os.getenv("SUPABASE_URL")
        if url:
            logger.debug(f"SUPABASE_URL loaded: {url}")
        else:
            logger.error("SUPABASE_URL not found in environment")
        return url

    @property
    def SUPABASE_ANON_KEY(self) -> Optional[str]:
        key = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY"))
        if key:
            logger.debug(f"SUPABASE_ANON_KEY loaded: {key[:20]}...")
        else:
            logger.error("SUPABASE_ANON_KEY not found in environment")
        return key

    @property
    def SUPABASE_SERVICE_ROLE_KEY(self) -> Optional[str]:
        return os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    @property
    def DATABASE_URL(self) -> Optional[str]:
        return os.getenv("DATABASE_URL")

    # Redis Configuration
    @property
    def REDIS_URL(self) -> Optional[str]:
        url = os.getenv("REDIS_URL")
        if url:
            logger.debug(f"REDIS_URL loaded: {url[:30]}...")
        return url

    @property
    def REDIS_HOST(self) -> str:
        return os.getenv("REDIS_HOST", "localhost")

    @property
    def REDIS_PORT(self) -> int:
        return int(os.getenv("REDIS_PORT", "6379"))

    @property
    def REDIS_PASSWORD(self) -> Optional[str]:
        return os.getenv("REDIS_PASSWORD")

    @property
    def REDIS_USERNAME(self) -> Optional[str]:
        return os.getenv("REDIS_USERNAME", "default")

    @property
    def REDIS_TLS(self) -> bool:
        return os.getenv("REDIS_TLS", "false").lower() == "true"

    # File Processing
    @property
    def MAX_FILE_SIZE(self) -> int:
        return int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024

    @property
    def UPLOAD_DIR(self) -> str:
        return os.getenv("UPLOAD_DIR", "uploads")

    @property
    def PROCESSED_DIR(self) -> str:
        return os.getenv("PROCESSED_DIR", "processed")

    # AI/ML Configuration
    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        return os.getenv("OPENAI_API_KEY")

    @property
    def EMBEDDING_MODEL(self) -> str:
        return os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    @property
    def CHUNK_SIZE(self) -> int:
        return int(os.getenv("CHUNK_SIZE", "384"))

    # Logging Configuration
    @property
    def LOG_LEVEL(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def LOG_FILE(self) -> Optional[str]:
        return os.getenv("LOG_FILE")

    # Security
    @property
    def API_KEY(self) -> Optional[str]:
        return os.getenv("API_KEY")

    @property
    def SECRET_KEY(self) -> str:
        return os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")

    # Cache Settings
    @property
    def CACHE_TTL(self) -> int:
        return int(os.getenv("CACHE_TTL", "3600"))

    @property
    def CACHE_EXPIRY_HOURS(self) -> int:
        return int(os.getenv("CACHE_EXPIRY_HOURS", "24"))

    # Feature Flags
    @property
    def ENABLE_REDIS_CACHE(self) -> bool:
        return os.getenv("ENABLE_REDIS_CACHE", "true").lower() == "true"

    @property
    def ENABLE_SUMMARIZATION(self) -> bool:
        return os.getenv("ENABLE_SUMMARIZATION", "true").lower() == "true"

    def is_valid(self) -> Tuple[bool, List[str]]:
        """Check if configuration is valid"""
        errors = []

        if not self.SUPABASE_URL:
            errors.append("SUPABASE_URL is required")

        if not self.SUPABASE_ANON_KEY:
            errors.append("SUPABASE_ANON_KEY is required")

        # Validate URLs if provided
        if self.SUPABASE_URL and not self.SUPABASE_URL.startswith(('http://', 'https://')):
            errors.append("SUPABASE_URL must be a valid URL")

        return len(errors) == 0, errors

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings (excluding sensitive data)"""
        settings = {}
        sensitive_keys = {'SUPABASE_SERVICE_ROLE_KEY', 'REDIS_PASSWORD', 'OPENAI_API_KEY', 'API_KEY', 'SECRET_KEY'}

        for attr_name in dir(self):
            if not attr_name.startswith('_') and attr_name.isupper():
                try:
                    value = getattr(self, attr_name)
                    if attr_name in sensitive_keys:
                        settings[attr_name] = "***" if value else None
                    else:
                        settings[attr_name] = value
                except Exception as e:
                    settings[attr_name] = f"Error: {e}"

        return settings

    def debug_environment(self):
        """Debug method to show environment loading status"""
        logger.info("=== Environment Debug Information ===")
        logger.info(f"Current working directory: {Path.cwd()}")
        logger.info(f"Script location: {Path(__file__).parent}")

        # Check for .env files
        possible_locations = [
            Path.cwd() / ".env",
            Path.cwd() / "config" / ".env",
            Path(__file__).parent / ".env",
            Path(__file__).parent.parent / ".env",
        ]

        logger.info("Checking for .env files:")
        for location in possible_locations:
            exists = location.exists()
            logger.info(f"  {location}: {'EXISTS' if exists else 'NOT FOUND'}")
            if exists:
                try:
                    with open(location, 'r') as f:
                        lines = f.readlines()
                        logger.info(f"    Contains {len(lines)} lines")
                        # Show first few non-comment lines
                        for i, line in enumerate(lines[:5]):
                            if line.strip() and not line.startswith('#'):
                                key = line.split('=')[0] if '=' in line else line.strip()
                                logger.info(f"    Line {i + 1}: {key}=...")
                except Exception as e:
                    logger.error(f"    Error reading file: {e}")

        # Check key environment variables
        key_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY', 'REDIS_URL']
        logger.info("Key environment variables:")
        for var in key_vars:
            value = os.getenv(var)
            if value:
                masked = value[:15] + "..." if len(value) > 15 else value
                logger.info(f"  {var}: {masked}")
            else:
                logger.info(f"  {var}: NOT SET")


# Singleton instance
_config_instance = None


def get_settings() -> EnvironmentConfig:
    """Get configuration singleton"""
    global _config_instance
    if _config_instance is None:
        _config_instance = EnvironmentConfig()
    return _config_instance


def reload_settings(env_file: Optional[str] = None) -> EnvironmentConfig:
    """Reload configuration (useful for testing)"""
    global _config_instance
    _config_instance = EnvironmentConfig(env_file)
    return _config_instance


# Utility function for debugging
def debug_environment():
    """Debug environment loading"""
    config = get_settings()
    config.debug_environment()