"""
Database connection management for Multi-Tenant Grade Insight

This module handles:
1. Connecting to different database shards
2. Managing connection pools
3. Routing tenants to the correct shard
4. Creating database sessions with proper tenant context
"""

import asyncio
from typing import Dict, Optional, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database.models import Base, TenantRegistry


class DatabaseManager:
    """
    Manages database connections across multiple shards.
    
    This class is responsible for:
    - Creating and managing connection pools for each shard
    - Providing the correct database session for a given tenant
    - Handling both sync and async database operations
    """
    
    def __init__(self):
        self.shard_engines: Dict[int, any] = {}
        self.shard_session_makers: Dict[int, any] = {}
        self.tenant_registry_engine = None
        self.tenant_registry_session_maker = None
        self._initialized = False
    
    async def initialize(self):
        """
        Initialize all database connections and create tables.
        
        This should be called once when the application starts.
        """
        if self._initialized:
            return
        
        print("🔄 Initializing database connections...")
        
        # Initialize tenant registry database
        await self._initialize_tenant_registry()
        
        # Initialize shard databases
        await self._initialize_shards()
        
        self._initialized = True
        print("✅ Database connections initialized successfully!")
    
    async def _initialize_tenant_registry(self):
        """Initialize the tenant registry database"""
        print("📋 Setting up tenant registry database...")
        
        # Create async engine for tenant registry
        self.tenant_registry_engine = create_async_engine(
            settings.tenant_registry_url,
            echo=settings.debug,  # Show SQL queries in debug mode
            pool_pre_ping=True,   # Verify connections before use
        )
        
        # Create session maker
        self.tenant_registry_session_maker = async_sessionmaker(
            self.tenant_registry_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables
        async with self.tenant_registry_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def _initialize_shards(self):
        """Initialize all shard databases"""
        for shard_number, database_url in settings.database_shard_urls.items():
            print(f"🗄️  Setting up shard {shard_number}...")
            
            # Create async engine for this shard
            engine = create_async_engine(
                database_url,
                echo=settings.debug,
                pool_pre_ping=True,
                # Connection pool settings
                pool_size=10,
                max_overflow=20,
            )
            
            # Create session maker
            session_maker = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Store in our dictionaries
            self.shard_engines[shard_number] = engine
            self.shard_session_makers[shard_number] = session_maker
            
            # Create tables for this shard
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
    
    async def get_tenant_shard(self, tenant_id: str) -> int:
        """
        Get the shard number for a specific tenant.
        
        This queries the tenant registry to find which shard
        a tenant's data is stored in.
        
        Args:
            tenant_id: The tenant identifier
            
        Returns:
            Shard number where the tenant's data is stored
            
        Raises:
            ValueError: If tenant is not found
        """
        async with self.get_tenant_registry_session() as session:
            from sqlalchemy import select
            
            # Query the tenant registry
            stmt = select(TenantRegistry).where(TenantRegistry.tenant_id == tenant_id)
            result = await session.execute(stmt)
            tenant_record = result.scalar_one_or_none()
            
            if not tenant_record:
                raise ValueError(f"Tenant '{tenant_id}' not found in registry")
            
            if not tenant_record.is_active:
                raise ValueError(f"Tenant '{tenant_id}' is not active")
            
            return tenant_record.shard_number
    
    @asynccontextmanager
    async def get_tenant_session(self, tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session for a specific tenant.
        
        This automatically routes to the correct shard and provides
        a database session that can be used to query tenant data.
        
        Args:
            tenant_id: The tenant identifier
            
        Yields:
            AsyncSession: Database session for the tenant's shard
            
        Example:
            async with db_manager.get_tenant_session("lincoln-high") as session:
                # Query student data for Lincoln High School
                students = await session.execute(select(Student))
        """
        if not self._initialized:
            await self.initialize()
        
        # Find which shard this tenant uses
        shard_number = await self.get_tenant_shard(tenant_id)
        
        # Get the session maker for this shard
        session_maker = self.shard_session_makers[shard_number]
        
        # Create and yield the session
        async with session_maker() as session:
            # Store tenant_id in session for middleware to use
            session.info['tenant_id'] = tenant_id
            session.info['shard_number'] = shard_number
            yield session
    
    @asynccontextmanager
    async def get_tenant_registry_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a session for the tenant registry database.
        
        This is used for managing tenant metadata and routing information.
        """
        if not self._initialized:
            await self.initialize()
        
        async with self.tenant_registry_session_maker() as session:
            yield session
    
    async def create_tenant(self, tenant_id: str, tenant_name: str, subdomain: str) -> TenantRegistry:
        """
        Create a new tenant in the system.
        
        This adds the tenant to the registry and assigns them to a shard.
        
        Args:
            tenant_id: Unique identifier for the tenant
            tenant_name: Display name (e.g., "Lincoln High School")
            subdomain: Subdomain for routing (e.g., "lincoln-high")
            
        Returns:
            TenantRegistry: The created tenant record
        """
        # Determine which shard to assign this tenant to
        shard_number = await self._get_least_loaded_shard()
        
        # Create tenant record
        tenant_record = TenantRegistry(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            subdomain=subdomain,
            shard_number=shard_number,
            is_active=True
        )
        
        # Save to tenant registry
        async with self.get_tenant_registry_session() as session:
            session.add(tenant_record)
            await session.commit()
            await session.refresh(tenant_record)
        
        print(f"✅ Created tenant '{tenant_name}' ({tenant_id}) on shard {shard_number}")
        return tenant_record
    
    async def _get_least_loaded_shard(self) -> int:
        """
        Find the shard with the fewest tenants.
        
        This helps distribute tenants evenly across shards.
        """
        async with self.get_tenant_registry_session() as session:
            from sqlalchemy import select, func
            
            # Count tenants per shard
            stmt = select(
                TenantRegistry.shard_number,
                func.count(TenantRegistry.id).label('tenant_count')
            ).group_by(TenantRegistry.shard_number)
            
            result = await session.execute(stmt)
            shard_counts = {row.shard_number: row.tenant_count for row in result}
        
        # Find shard with minimum tenants
        available_shards = list(settings.database_shard_urls.keys())
        
        if not shard_counts:
            # No tenants yet, use first shard
            return available_shards[0]
        
        # Return shard with fewest tenants
        return min(available_shards, key=lambda s: shard_counts.get(s, 0))
    
    async def get_tenant_by_subdomain(self, subdomain: str) -> Optional[TenantRegistry]:
        """
        Find a tenant by their subdomain.
        
        Used for routing HTTP requests to the correct tenant.
        
        Args:
            subdomain: The subdomain to look up
            
        Returns:
            TenantRegistry record if found, None otherwise
        """
        async with self.get_tenant_registry_session() as session:
            from sqlalchemy import select
            
            stmt = select(TenantRegistry).where(
                TenantRegistry.subdomain == subdomain,
                TenantRegistry.is_active == True
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def close_all_connections(self):
        """
        Close all database connections.
        
        This should be called when the application shuts down.
        """
        print("🔌 Closing database connections...")
        
        # Close shard engines
        for shard_number, engine in self.shard_engines.items():
            await engine.dispose()
            print(f"   Closed shard {shard_number}")
        
        # Close tenant registry engine
        if self.tenant_registry_engine:
            await self.tenant_registry_engine.dispose()
            print("   Closed tenant registry")
        
        print("✅ All database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


# Convenience functions for common operations

async def get_tenant_db_session(tenant_id: str):
    """
    Convenience function to get a tenant database session.
    
    This is what most of the application code will use.
    """
    return db_manager.get_tenant_session(tenant_id)


async def get_registry_db_session():
    """
    Convenience function to get a tenant registry session.
    """
    return db_manager.get_tenant_registry_session()


async def initialize_database():
    """
    Initialize the database system.
    
    Call this once when the application starts.
    """
    await db_manager.initialize()


async def create_new_tenant(tenant_id: str, tenant_name: str, subdomain: str):
    """
    Create a new tenant.
    
    Convenience function for tenant creation.
    """
    return await db_manager.create_tenant(tenant_id, tenant_name, subdomain)


# Example usage and testing
if __name__ == "__main__":
    async def main():
        """Test the database connection system"""
        print("Testing Multi-Tenant Database Connection System")
        print("=" * 50)
        
        # Initialize the database
        await initialize_database()
        
        # Create a test tenant
        tenant = await create_new_tenant(
            tenant_id="test-school",
            tenant_name="Test Elementary School",
            subdomain="test-school"
        )
        print(f"Created tenant: {tenant}")
        
        # Test tenant session
        async with get_tenant_db_session("test-school") as session:
            print(f"Got session for tenant: {session.info.get('tenant_id')}")
            print(f"Using shard: {session.info.get('shard_number')}")
        
        # Clean up
        await db_manager.close_all_connections()
    
    # Run the test
    asyncio.run(main())
