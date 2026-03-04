# ============================================================
# Model Manager - Automatic Fallback on Rate Limits
# Place in: utils/model_manager.py
# ============================================================

from autogen_ext.models.ollama import OllamaChatCompletionClient
from config.settings import settings
from loguru import logger
from datetime import datetime, timedelta
import json
from pathlib import Path


class ModelManager:
    """
    Manages model selection with automatic fallback
    
    Features:
    - Detects rate limit errors
    - Automatically switches to fallback model (qwen3-vl)
    - Returns to primary model after cooldown period
    - Tracks usage and failures
    """
    
    def __init__(self):
        self.primary_model = settings.ollama_model  # gpt-oss:120b-cloud
        self.fallback_model = "qwen3-vl"  # Local fallback
        
        self.current_model = self.primary_model
        self.using_fallback = False
        
        self.rate_limit_cooldown = 60  # minutes
        self.rate_limit_until = None
        
        self.failure_count = 0
        self.failure_threshold = 3  # Switch after 3 failures
        
        self.usage_file = Path("logs/model_usage.json")
        self.usage_file.parent.mkdir(exist_ok=True)
        
        logger.info(f"🎮 ModelManager initialized")
        logger.info(f"   Primary: {self.primary_model}")
        logger.info(f"   Fallback: {self.fallback_model}")
    
    def get_model_client(self) -> OllamaChatCompletionClient:
        """
        Get current model client
        
        Returns appropriate model based on:
        - Rate limit status
        - Failure count
        - Cooldown period
        """
        
        # Check if we should return to primary model
        if self.using_fallback and self.rate_limit_until:
            if datetime.now() > self.rate_limit_until:
                logger.info(f"⏰ Cooldown expired, returning to primary model: {self.primary_model}")
                self.using_fallback = False
                self.current_model = self.primary_model
                self.failure_count = 0
                self.rate_limit_until = None
        
        # Determine which model to use
        model_to_use = self.fallback_model if self.using_fallback else self.primary_model
        
        logger.debug(f"🎯 Using model: {model_to_use} (fallback={self.using_fallback})")
        
        # Create client
        client = OllamaChatCompletionClient(
            model=model_to_use,
            base_url=settings.ollama_host,
            temperature=0.7,
            max_tokens=2000,
            model_info=settings.ollama_model_info if model_to_use == self.primary_model else None
        )
        
        return client
    
    def handle_model_error(self, error: Exception) -> bool:
        """
        Handle model execution error
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if switched to fallback, False otherwise
        """
        
        error_str = str(error).lower()
        
        # Check for rate limit indicators
        rate_limit_keywords = [
            "rate limit",
            "too many requests",
            "429",
            "quota exceeded",
            "limit exceeded",
            "throttle"
        ]
        
        is_rate_limit = any(keyword in error_str for keyword in rate_limit_keywords)
        
        if is_rate_limit:
            logger.warning(f"🚨 Rate limit detected: {error}")
            self._switch_to_fallback("Rate limit exceeded")
            return True
        
        # Check for repeated failures
        self.failure_count += 1
        logger.warning(f"⚠️ Model failure #{self.failure_count}: {error}")
        
        if self.failure_count >= self.failure_threshold:
            logger.error(f"🚨 Failure threshold reached ({self.failure_threshold})")
            self._switch_to_fallback(f"Too many failures ({self.failure_count})")
            return True
        
        return False
    
    def _switch_to_fallback(self, reason: str):
        """Switch to fallback model"""
        
        if self.using_fallback:
            logger.warning(f"⚠️ Already using fallback model")
            return
        
        logger.warning(f"🔄 Switching to fallback model: {self.fallback_model}")
        logger.warning(f"   Reason: {reason}")
        logger.warning(f"   Cooldown: {self.rate_limit_cooldown} minutes")
        
        self.using_fallback = True
        self.current_model = self.fallback_model
        self.rate_limit_until = datetime.now() + timedelta(minutes=self.rate_limit_cooldown)
        
        self._log_usage("switched_to_fallback", reason)
    
    def report_success(self):
        """Report successful execution"""
        
        # Reset failure count on success
        if self.failure_count > 0:
            logger.debug(f"✅ Success - resetting failure count (was {self.failure_count})")
            self.failure_count = 0
        
        self._log_usage("success", self.current_model)
    
    def _log_usage(self, event: str, details: str):
        """Log usage to file"""
        
        try:
            # Load existing data
            if self.usage_file.exists():
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {"events": []}
            
            # Add new event
            data["events"].append({
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "details": details,
                "current_model": self.current_model,
                "using_fallback": self.using_fallback
            })
            
            # Keep only last 1000 events
            data["events"] = data["events"][-1000:]
            
            # Save
            with open(self.usage_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
    
    def get_status(self) -> dict:
        """Get current manager status"""
        
        return {
            "current_model": self.current_model,
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "using_fallback": self.using_fallback,
            "failure_count": self.failure_count,
            "rate_limit_until": self.rate_limit_until.isoformat() if self.rate_limit_until else None,
            "cooldown_minutes": self.rate_limit_cooldown
        }


# Singleton instance
model_manager = ModelManager()
