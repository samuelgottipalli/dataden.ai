"""
Usage Tracker - Monitor API usage and enforce quotas
File: utils/usage_tracker.py (NEW FILE)
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger
import json
import os
from pathlib import Path

class UsageTracker:
    """Track API usage to prevent quota exhaustion"""
    
    def __init__(self, daily_limit: int = 1000, warn_percentage: float = 0.8):
        self.daily_limit = daily_limit
        self.warn_percentage = warn_percentage
        self.usage_file = Path("logs/usage_tracking.json")
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing usage data
        self.data = self._load_usage_data()
    
    def _load_usage_data(self) -> Dict:
        """Load usage data from file"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load usage data: {e}")
        
        # Return default structure
        return {
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "requests_today": 0,
            "tokens_today": 0,
            "requests_total": 0,
            "tokens_total": 0,
            "last_warning_at": None,
            "fallback_count": 0
        }
    
    def _save_usage_data(self):
        """Save usage data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save usage data: {e}")
    
    def _check_date_reset(self):
        """Reset daily counters if new day"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self.data["current_date"] != current_date:
            logger.info(f"New day detected, resetting daily counters")
            self.data["current_date"] = current_date
            self.data["requests_today"] = 0
            self.data["tokens_today"] = 0
            self.data["last_warning_at"] = None
            self._save_usage_data()
    
    def record_request(self, tokens_used: int = 0, model: str = "primary"):
        """Record a request and token usage"""
        self._check_date_reset()
        
        # Increment counters
        self.data["requests_today"] += 1
        self.data["requests_total"] += 1
        self.data["tokens_today"] += tokens_used
        self.data["tokens_total"] += tokens_used
        
        # Track fallback usage
        if model == "fallback":
            self.data["fallback_count"] += 1
        
        # Save
        self._save_usage_data()
        
        logger.debug(f"Usage recorded: {self.data['requests_today']}/{self.daily_limit} requests today")
    
    def check_quota(self) -> Dict[str, any]:
        """
        Check if approaching or exceeded quota
        
        Returns:
            dict with: exceeded, approaching, percentage, remaining
        """
        self._check_date_reset()
        
        requests_today = self.data["requests_today"]
        percentage = requests_today / self.daily_limit
        remaining = self.daily_limit - requests_today
        
        exceeded = requests_today >= self.daily_limit
        approaching = percentage >= self.warn_percentage
        
        return {
            "exceeded": exceeded,
            "approaching": approaching,
            "percentage": percentage,
            "remaining": remaining,
            "used": requests_today,
            "limit": self.daily_limit
        }
    
    def should_warn_user(self) -> bool:
        """Check if we should warn user about quota"""
        quota_status = self.check_quota()
        
        # Don't spam warnings - only once when crossing threshold
        if quota_status["approaching"] and not self.data["last_warning_at"]:
            self.data["last_warning_at"] = datetime.now().isoformat()
            self._save_usage_data()
            return True
        
        return False
    
    def get_usage_summary(self) -> str:
        """Get human-readable usage summary"""
        self._check_date_reset()
        quota_status = self.check_quota()
        
        summary = f"""
📊 API Usage Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Today: {quota_status['used']}/{quota_status['limit']} requests ({quota_status['percentage']:.1%})
Remaining: {quota_status['remaining']} requests
Tokens used today: {self.data['tokens_today']:,}
Fallback usage: {self.data['fallback_count']} times

Total (all time):
  Requests: {self.data['requests_total']:,}
  Tokens: {self.data['tokens_total']:,}
"""
        return summary.strip()


# Global instance
_tracker = None

def get_usage_tracker() -> UsageTracker:
    """Get or create global usage tracker"""
    global _tracker
    if _tracker is None:
        from config.settings import settings
        _tracker = UsageTracker(
            daily_limit=settings.api_quota_daily_limit,
            warn_percentage=settings.api_quota_warn_percentage
        )
    return _tracker
