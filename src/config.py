# src/config.py
import os
import yaml
from typing import Dict, Any, List
from pathlib import Path

class Config:
    """Centralized configuration management"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "configs" / "settings.yml"
        
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file with environment variable overrides"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            config = {}
        
        # Override with environment variables
        config['google_api_key'] = os.getenv('GOOGLE_API_KEY', config.get('google_api_key', ''))
        config['google_cse_id'] = os.getenv('GOOGLE_CSE_ID', config.get('google_cse_id', ''))
        config['openai_api_key'] = os.getenv('OPENAI_API_KEY', config.get('openai_api_key', ''))
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with dot notation support"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value with dot notation support"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    # Convenience properties
    @property
    def google_api_key(self) -> str:
        return self.get('google_api_key', '')
    
    @property
    def google_cse_id(self) -> str:
        return self.get('google_cse_id', '')
    
    @property
    def openai_api_key(self) -> str:
        return self.get('openai_api_key', '')
    
    @property
    def engine_keywords(self) -> List[str]:
        return self.get('engine_keywords', [])
    
    @property
    def experience_levels(self) -> Dict[str, List[str]]:
        return self.get('experience_levels', {})
    
    @property
    def salary_ranges(self) -> Dict[str, List[int]]:
        return self.get('salary_ranges', {})
    
    @property
    def company_sizes(self) -> Dict[str, List[int]]:
        return self.get('company_sizes', {})
    
    @property
    def matching_weights(self) -> Dict[str, float]:
        return self.get('matching.weights', {})
    
    @property
    def matching_thresholds(self) -> Dict[str, float]:
        return self.get('matching.thresholds', {})
    
    @property
    def web_config(self) -> Dict[str, Any]:
        return self.get('web', {})
    
    @property
    def database_url(self) -> str:
        return self.get('database.url', 'sqlite:///data/db.sqlite')
    
    @property
    def performance_config(self) -> Dict[str, Any]:
        return self.get('performance', {})
    
    @property
    def analytics_config(self) -> Dict[str, Any]:
        return self.get('analytics', {})

# Global configuration instance
config = Config()
