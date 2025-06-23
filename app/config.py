"""
Configuration management for Multi-Tenant Grade Insight

This file handles all application settings and provides a clean way to access
configuration values throughout the application.
"""

import os
from typing import Dict, List, Optional
from pydantic import validator, field_validator
from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Pydantic automatically loads values from environment variables
    and validates them according to the type hints.
    """
    
    # Application Info
    app_name: str = "Multi-Tenant Grade Insight"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database Shards Configuration
    # These are the individual database URLs for each shard
    database_shard_1_url: str
    database_shard_2_url: Optional[str] = None
    database_shard_3_url: Optional[str] = None
    
    # Tenant Registry Database
    # This special database stores which tenant belongs to which shard
    tenant_registry_url: str
    
    # Redis for caching
    redis_url: str = "redis://localhost:6379/0"
    
    # Tenant Management
    max_tenants_per_shard: int = 1000
    default_shard: int = 1
    
    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    # File Upload Configuration
    max_file_size_mb: int = 50
    allowed_file_types: List[str] = [".csv", ".xlsx", ".xls"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # CORS (Cross-Origin Resource Sharing) for web browsers
    allow_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8080"
    ]
    cors_enabled: bool = True

    @field_validator('allow_origins', mode='before')
    @classmethod
    def parse_origins(cls, v):
        """Convert comma-separated string to list if needed"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    @property
    def database_shard_urls(self) -> Dict[int, str]:
        """
        Returns a dictionary mapping shard numbers to their database URLs.
        
        This makes it easy to look up which database to connect to
        for a given shard number.
        """
        shards = {1: self.database_shard_1_url}
        
        if self.database_shard_2_url:
            shards[2] = self.database_shard_2_url
        if self.database_shard_3_url:
            shards[3] = self.database_shard_3_url
            
        return shards
    
    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB to bytes for file size validation"""
        return self.max_file_size_mb * 1024 * 1024
    
    class Config:
        # Tell Pydantic to load from .env file
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Make field names case insensitive
        case_sensitive = False


# Create a global settings instance
# This will be imported and used throughout the application
settings = Settings()


def get_shard_for_tenant(tenant_id: str) -> int:
    """
    Determine which database shard a tenant should use.
    
    For now, this is a simple hash-based approach.
    In production, this would query the tenant registry service.
    
    Args:
        tenant_id: The unique identifier for the tenant (school)
        
    Returns:
        The shard number (1, 2, 3, etc.)
    """
    # Simple hash-based sharding for now
    # This ensures the same tenant always goes to the same shard
    tenant_hash = hash(tenant_id)
    available_shards = len(settings.database_shard_urls)
    
    return (tenant_hash % available_shards) + 1


def get_database_url_for_tenant(tenant_id: str) -> str:
    """
    Get the database URL for a specific tenant.
    
    Args:
        tenant_id: The unique identifier for the tenant
        
    Returns:
        The database URL for the tenant's shard
    """
    shard_number = get_shard_for_tenant(tenant_id)
    return settings.database_shard_urls[shard_number]


# Example usage and testing
if __name__ == "__main__":
    print(f"App: {settings.app_name} v{settings.app_version}")
    print(f"Available shards: {list(settings.database_shard_urls.keys())}")
    print(f"Debug mode: {settings.debug}")
    
    # Test tenant-to-shard mapping
    test_tenants = ["lincoln-high", "washington-middle", "jefferson-elementary"]
    for tenant in test_tenants:
        shard = get_shard_for_tenant(tenant)
        print(f"Tenant '{tenant}' -> Shard {shard}")
