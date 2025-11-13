"""
Model Manager - Handle primary and fallback models
File: utils/model_manager.py (NEW FILE)
"""

from loguru import logger
from typing import Optional, Tuple
from autogen_ext.models.openai import OllamaChatCompletionClient
from config.settings import settings

class ModelManager:
    """Manage primary and fallback model switching"""
    
    def __init__(self):
        self.primary_model = settings.ollama_model
        self.fallback_model = settings.ollama_fallback_model
        self.enable_fallback = settings.enable_fallback
        self.fallback_after_attempts = settings.fallback_after_attempts
        
        self.current_model = self.primary_model
        self.failure_count = 0
        self.using_fallback = False
    
    def get_model_client(self, force_fallback: bool = False) -> Tuple[OllamaChatCompletionClient, str]:
        """
        Get appropriate model client
        
        Returns:
            (model_client, model_name)
        """
        # Determine which model to use
        if force_fallback or (self.using_fallback and self.enable_fallback):
            model_name = self.fallback_model
            logger.info(f"🔄 Using fallback model: {model_name}")
        else:
            model_name = self.primary_model
            logger.debug(f"Using primary model: {model_name}")
        
        # Create client with INCREASED context length
        client = OllamaChatCompletionClient(
            model=model_name,
            base_url=settings.ollama_host,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,  # Now 8000!
        )
        
        return client, model_name
    
    def record_failure(self) -> bool:
        """
        Record a model failure
        
        Returns:
            True if should switch to fallback
        """
        self.failure_count += 1
        logger.warning(f"Model failure #{self.failure_count}")
        
        # Check if we should switch to fallback
        if (self.enable_fallback and 
            not self.using_fallback and 
            self.failure_count >= self.fallback_after_attempts):
            
            logger.warning(f"⚠️  Switching to fallback model after {self.failure_count} failures")
            self.using_fallback = True
            return True
        
        return False
    
    def record_success(self):
        """Record a successful request"""
        # Reset failure counter on success
        if self.failure_count > 0:
            logger.info("✓ Request successful, resetting failure counter")
            self.failure_count = 0
    
    def reset_to_primary(self):
        """Reset back to primary model"""
        if self.using_fallback:
            logger.info("Resetting to primary model")
            self.using_fallback = False
            self.failure_count = 0
    
    def get_fallback_notification(self) -> str:
        """Get user notification message about fallback"""
        if not self.using_fallback:
            return ""
        
        return f"""
🔄 **Notice: Using Fallback Model**

The primary cloud model is currently unavailable. I've switched to a local model ({self.fallback_model}).

**What this means:**
- ✅ Your request will still be processed
- ⚠️  Response quality may be slightly reduced
- ⚠️  Response time may be slower
- ✅ No data or context is lost

You can continue your conversation normally. The system will automatically switch back to the primary model when available.
"""

# Global instance
_model_manager = None

def get_model_manager() -> ModelManager:
    """Get or create global model manager"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
