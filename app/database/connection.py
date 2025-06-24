"""
Simple Database Connection Manager for Multi-Tenant Grade Insight
Handles routing tenants to the correct database shard
"""

import asyncio
from typing import Dict, Optional, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.database.models import Base, TenantRegistry


class DatabaseManager:
    """
    Simple database manager for multi-tenant grade system
    Routes tenants to the correct database shard
    """
    
    def __init__(self):
        self.shard_engines: Dict[int, any] = {}
        self.shard_session_makers: Dict[int, any] = {}
        self.registry_engine = None
        self.registry_session_maker = None
        self._initialized = False
    
    async def initialize(self, database_urls: Dict[int, str], registry_url: str):
        """
        Initialize database connections
        
        Args:
            database_urls: Dict mapping shard number to database URL
            registry_url: URL for the tenant registry database
        """
        if self._initialized:
            return
        
        print("🔄 Initializing database connections...")
        
        # Initialize tenant registry
        self.registry_engine = create_async_engine(registry_url, echo=False)
        self.registry_session_maker = async_sessionmaker(
            self.registry_engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create registry tables
        async with self.registry_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Initialize shards
        for shard_number, database_url in database_urls.items():
            print(f"🗄️  Setting up shard {shard_number}...")
            
            engine = create_async_engine(database_url, echo=False)
            session_maker = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            
            self.shard_engines[shard_number] = engine
            self.shard_session_makers[shard_number] = session_maker
            
            # Create tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        
        self._initialized = True
        print("✅ Database connections initialized!")
    
    async def get_tenant_shard(self, tenant_id: str) -> int:
        """Get the shard number for a tenant"""
        async with self.get_registry_session() as session:
            stmt = select(TenantRegistry).where(
                TenantRegistry.tenant_id == tenant_id,
                TenantRegistry.is_active == True
            )
            result = await session.execute(stmt)
            tenant_record = result.scalar_one_or_none()
            
            if not tenant_record:
                raise ValueError(f"Tenant '{tenant_id}' not found")
            
            return tenant_record.shard_number
    
    @asynccontextmanager
    async def get_tenant_session(self, tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session for a specific tenant"""
        shard_number = await self.get_tenant_shard(tenant_id)
        session_maker = self.shard_session_makers[shard_number]
        
        async with session_maker() as session:
            # Store tenant info in session for easy access
            session.info['tenant_id'] = tenant_id
            session.info['shard_number'] = shard_number
            yield session
    
    @asynccontextmanager
    async def get_registry_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a session for the tenant registry"""
        async with self.registry_session_maker() as session:
            yield session
    
    async def create_tenant(self, tenant_id: str, tenant_name: str, admin_email: str, subdomain: str = None) -> TenantRegistry:
        """Create a new tenant and assign to a shard"""
        # Simple round-robin shard assignment
        shard_number = await self._get_next_shard()
        
        tenant_record = TenantRegistry(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            subdomain=subdomain,
            shard_number=shard_number,
            admin_email=admin_email,
            is_active=True
        )
        
        async with self.get_registry_session() as session:
            session.add(tenant_record)
            await session.commit()
            await session.refresh(tenant_record)
        
        print(f"✅ Created tenant '{tenant_name}' on shard {shard_number}")
        return tenant_record
    
    async def get_tenant_by_subdomain(self, subdomain: str) -> Optional[TenantRegistry]:
        """Find tenant by subdomain for routing"""
        async with self.get_registry_session() as session:
            stmt = select(TenantRegistry).where(
                TenantRegistry.subdomain == subdomain,
                TenantRegistry.is_active == True
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def _get_next_shard(self) -> int:
        """Simple round-robin shard assignment"""
        available_shards = list(self.shard_engines.keys())
        if not available_shards:
            raise ValueError("No database shards available")
        
        # Count tenants per shard and return the one with fewest
        async with self.get_registry_session() as session:
            shard_counts = {}
            for shard in available_shards:
                stmt = select(TenantRegistry).where(TenantRegistry.shard_number == shard)
                result = await session.execute(stmt)
                shard_counts[shard] = len(result.all())
        
        # Return shard with minimum tenants
        return min(available_shards, key=lambda s: shard_counts.get(s, 0))
    
    async def close_all_connections(self):
        """Close all database connections"""
        for engine in self.shard_engines.values():
            await engine.dispose()
        
        if self.registry_engine:
            await self.registry_engine.dispose()
        
        print("✅ All database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


# Convenience functions
async def get_tenant_db_session(tenant_id: str):
    """Get a database session for a tenant"""
    return db_manager.get_tenant_session(tenant_id)


async def get_registry_db_session():
    """Get a session for the tenant registry"""
    return db_manager.get_registry_session()


async def initialize_database(database_urls: Dict[int, str], registry_url: str):
    """Initialize the database system"""
    await db_manager.initialize(database_urls, registry_url)


async def create_new_tenant(tenant_id: str, tenant_name: str, admin_email: str, subdomain: str = None):
    """Create a new tenant"""
    return await db_manager.create_tenant(tenant_id, tenant_name, admin_email, subdomain)


# Example usage
if __name__ == "__main__":
    async def main():
        # Example database URLs
        database_urls = {
            1: "postgresql+asyncpg://user:pass@localhost:5432/grades_shard1",
            2: "postgresql+asyncpg://user:pass@localhost:5433/grades_shard2",
            3: "postgresql+asyncpg://user:pass@localhost:5434/grades_shard3"
        }
        registry_url = "postgresql+asyncpg://user:pass@localhost:5435/tenant_registry"
        
        # Initialize
        await initialize_database(database_urls, registry_url)
        
        # Create a test tenant
        tenant = await create_new_tenant(
            tenant_id="lincoln-high",
            tenant_name="Lincoln High School", 
            admin_email="admin@lincolnhigh.edu",
            subdomain="lincoln-high"
        )
        print(f"Created: {tenant}")
        
        # Test tenant session
        async with get_tenant_db_session("lincoln-high") as session:
            print(f"Got session for: {session.info.get('tenant_id')}")
        
        # Clean up
        await db_manager.close_all_connections()
    
    asyncio.run(main())
