# Simple Model Manager with Rate Limit Fallback
# File: utils/model_manager.py

from loguru import logger
from autogen_ext.models.ollama import OllamaChatCompletionClient
from config.settings import settings
import time
from typing import Optional


class ModelManager:
    """
    Manages model selection with automatic fallback

    Primary: gpt-oss:120b-cloud (powerful, shared, rate limited)
    Fallback: qwen3-vl (local, no rate limit, slower)
    """

    def __init__(self):
        self.primary_model = settings.ollama_model  # gpt-oss:120b-cloud from settings
        self.fallback_model = "qwen3-vl"  # Local model as fallback

        self.fallback_active = False
        self.rate_limit_until = None
        self.failure_count = 0

        logger.info(f"📊 Model Manager initialized")
        logger.info(f"  Primary model: {self.primary_model}")
        logger.info(f"  Fallback model: {self.fallback_model}")

    def get_model_client(self) -> OllamaChatCompletionClient:
        """
        Get appropriate model client

        Automatically uses fallback if primary is rate limited
        """

        # Check if rate limit period expired
        if self.rate_limit_until and time.time() > self.rate_limit_until:
            logger.info(
                "⏰ Rate limit cooldown expired, switching back to primary model"
            )
            self.fallback_active = False
            self.rate_limit_until = None
            self.failure_count = 0

        # Determine which model to use
        model_name = self.fallback_model if self.fallback_active else self.primary_model

        # Create client
        client = OllamaChatCompletionClient(
            model=model_name,
            base_url=settings.ollama_host,
            temperature=0.7,
            max_tokens=2000,
            model_info=settings.ollama_model_info,
        )

        if self.fallback_active:
            logger.debug(f"🔄 Using fallback model: {model_name}")

        return client

    def handle_rate_limit(self, cooldown_minutes: int = 60):
        """
        Switch to fallback model due to rate limit

        Args:
            cooldown_minutes: How long to wait before retrying primary (default: 60 min)
        """

        if not self.fallback_active:
            logger.warning(f"⚠️ RATE LIMIT DETECTED on {self.primary_model}")
            logger.info(f"🔄 Switching to fallback model: {self.fallback_model}")
            logger.info(f"⏰ Will retry primary model in {cooldown_minutes} minutes")
            logger.info(
                f"💡 Note: Fallback model is local and may be slower but has no rate limits"
            )

            self.fallback_active = True
            self.rate_limit_until = time.time() + (cooldown_minutes * 60)
            self.failure_count += 1

    def handle_model_failure(self, error_message: str) -> bool:
        """
        Check if error indicates rate limit and handle it

        Returns:
            True if rate limit detected and handled, False otherwise
        """

        # Rate limit indicators
        rate_limit_keywords = [
            "rate limit",
            "too many requests",
            "quota exceeded",
            "429",
            "limit reached",
            "throttle",
            "capacity",
        ]

        error_lower = str(error_message).lower()

        # Check for rate limit indicators
        for keyword in rate_limit_keywords:
            if keyword in error_lower:
                self.handle_rate_limit()
                return True

        return False

    def is_using_fallback(self) -> bool:
        """Check if currently using fallback model"""
        return self.fallback_active

    def get_current_model_name(self) -> str:
        """Get name of currently active model"""
        return self.fallback_model if self.fallback_active else self.primary_model

    def get_status(self) -> dict:
        """Get current status for debugging"""
        return {
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "active_model": self.get_current_model_name(),
            "using_fallback": self.fallback_active,
            "rate_limit_until": self.rate_limit_until,
            "failure_count": self.failure_count,
        }


# Global singleton instance
model_manager = ModelManager()
