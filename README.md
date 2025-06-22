# Grade Insight — Multi-Tenant Architecture

**Grade Insight** is a scalable, multi-tenant FastAPI application designed to manage student grades for thousands of schools. It supports CSV grade uploads with strong data isolation, high availability, and auto-scaling on Kubernetes.

---

## Current State

- Single-tenant FastAPI app with CSV uploads
- SQLite database managing students and grades
- Docker-ready with a responsive web interface
- [GitHub Repository](https://github.com/thorlorick/database_gradeinsight)

---

## Target Architecture

### Tenant Resolution

- Subdomain routing, e.g. `school1.gradeinsight.com`, `school2.gradeinsight.com`
- Row-level isolation via `tenant_id` in all database tables
- Supports fallback with custom header `X-Tenant-ID` or JWT tokens

### Database Sharding

- Migrating from SQLite to PostgreSQL shards
- Shards assigned by school ranges, e.g. shard_1 for schools 1–1000
- Multi-tenant schemas with row-level security (RLS) policies to enforce isolation

### Kubernetes Infrastructure

- Ingress Controller routes subdomains to tenant-aware FastAPI pods
- FastAPI pods autoscale horizontally and vertically based on load
- PostgreSQL StatefulSets deployed per shard for data persistence and scaling
- Tenant Registry Service to manage tenant-to-shard mappings

### Auto-Scaling Strategy

- Horizontal Pod Autoscaler (HPA) adjusts pods by tenant load
- Vertical Pod Autoscaler (VPA) optimizes resource allocation
- Cluster Autoscaler adjusts cluster nodes dynamically
- Custom metrics for tenant-specific performance and usage

---

## Implementation Phases

1. **Database sharding + Tenant Registry Service**  
2. **FastAPI tenant middleware + Multi-tenant data models**  
3. **Kubernetes deployment + Tenant-aware routing**  
4. **Tenant provisioning pipeline + Monitoring and alerting**

---

## Key Benefits

- Cost-efficient shared infrastructure  
- Strong data isolation between tenants  
- Auto-scaling based on real-time usage  
- Maintains existing Grade Insight features  
- Single codebase serving all tenants  

---

## Migration Path

1. Migrate SQLite → PostgreSQL shards  
2. Add `tenant_id` filtering to all queries  
3. Deploy on Kubernetes with tenant-aware routing  
4. Enable subdomain-based tenant resolution  
5. Set up auto-scaling based on tenant metrics  

---

# Docker Setup for Multi-Tenant Grade Insight

This guide will help you containerize and run your Multi-Tenant Grade Insight application using Docker.

## Prerequisites

- Docker (version 20.10+)
- Docker Compose (version 2.0+)
- At least 4GB RAM available for containers

## Quick Start

1. **Clone your repository**:
   ```bash
   git clone https://github.com/thorlorick/multiTenantGradeInsight.git
   cd multiTenantGradeInsight
   ```

2. **Create environment file**:
   ```bash
   cp .env.docker .env
   ```
   
   Edit `.env` and update the secret keys and any other settings specific to your environment.

3. **Build and run the application**:
   ```bash
   # Start all services
   docker-compose up -d
   
   # View logs
   docker-compose logs -f gradeinsight-app
   ```

4. **Access the application**:
   - Main application: http://localhost:8000
   - Health check: http://localhost:8000/health

## Services Architecture

The Docker setup includes:

- **gradeinsight-app**: Your FastAPI application
- **postgres-shard-1**: PostgreSQL database for schools 1-1000
- **postgres-shard-2**: PostgreSQL database for schools 1001-2000  
- **postgres-shard-3**: PostgreSQL database for schools 2001-3000
- **postgres-registry**: Tenant registry database
- **redis**: Caching and session storage
- **nginx**: Reverse proxy (production profile only)

## Database Ports

- Shard 1: localhost:5432
- Shard 2: localhost:5433
- Shard 3: localhost:5434
- Registry: localhost:5435
- Redis: localhost:6379

## Environment Configuration

Key environment variables to customize:

```bash
# Security (REQUIRED - Change these!)
SECRET_KEY=your-super-secret-key-min-32-chars
JWT_SECRET_KEY=your-jwt-secret-key-min-32-chars

# Database connections
DATABASE_SHARD_1_URL=postgresql+asyncpg://gradeuser:gradepass@postgres-shard-1:5432/gradeinsight_shard1

# CORS for your domain
ALLOW_ORIGINS=https://school1.yourdomain.com,https://school2.yourdomain.com
```

## Development vs Production

### Development
```bash
# Start with development settings
docker-compose up -d

# Enable debug mode
docker-compose exec gradeinsight-app sh -c "export DEBUG=true && uvicorn app.main:app --reload --host 0.0.0.0"
```

### Production
```bash
# Start with production profile (includes Nginx)
docker-compose --profile production up -d

# Scale the application
docker-compose up -d --scale gradeinsight-app=3
```

## Database Initialization

The databases will be automatically initialized when first started. If you need to run migrations:

```bash
# Run database migrations
docker-compose exec gradeinsight-app alembic upgrade head

# Connect to a specific shard
docker-compose exec postgres-shard-1 psql -U gradeuser -d gradeinsight_shard1
```

## Common Commands

```bash
# View all container status
docker-compose ps

# View logs for specific service
docker-compose logs -f gradeinsight-app
docker-compose logs -f postgres-shard-1

# Restart a service
docker-compose restart gradeinsight-app

# Scale the application
docker-compose up -d --scale gradeinsight-app=2

# Execute commands in container
docker-compose exec gradeinsight-app bash
docker-compose exec postgres-shard-1 psql -U gradeuser

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: This deletes data!)
docker-compose down -v
```

## Monitoring and Health Checks

- Application health: http://localhost:8000/health
- Container health: `docker-compose ps` (shows health status)
- Application metrics: http://localhost:8000/metrics (if Prometheus is configured)

## Backup and Restore

### Backup
```bash
# Backup all databases
docker-compose exec postgres-shard-1 pg_dump -U gradeuser gradeinsight_shard1 > backup_shard1.sql
docker-compose exec postgres-shard-2 pg_dump -U gradeuser gradeinsight_shard2 > backup_shard2.sql
docker-compose exec postgres-shard-3 pg_dump -U gradeuser gradeinsight_shard3 > backup_shard3.sql
docker-compose exec postgres-registry pg_dump -U gradeuser tenant_registry > backup_registry.sql
```

### Restore
```bash
# Restore a database
docker-compose exec -T postgres-shard-1 psql -U gradeuser gradeinsight_shard1 < backup_shard1.sql
```

## Troubleshooting

### Application won't start
1. Check environment variables: `docker-compose config`
2. Check application logs: `docker-compose logs gradeinsight-app`
3. Verify database connectivity: `docker-compose exec gradeinsight-app python -c "from app.database.connection import db_manager; print('DB OK')"`

### Database connection issues
1. Check if databases are running: `docker-compose ps`
2. Test database connection: `docker-compose exec postgres-shard-1 psql -U gradeuser -l`
3. Check network connectivity: `docker-compose exec gradeinsight-app ping postgres-shard-1`

### Performance issues
1. Monitor resource usage: `docker stats`
2. Scale the application: `docker-compose up -d --scale gradeinsight-app=3`
3. Tune database connections in `.env`

### Port conflicts
If you get port binding errors, modify the ports in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Change external port
```

## Security Considerations

1. **Change default passwords** in production
2. **Use secrets management** for sensitive data
3. **Enable SSL/TLS** with proper certificates
4. **Limit network exposure** using Docker networks
5. **Regular security updates** of base images

## Next Steps

1. Set up SSL certificates for HTTPS
2. Configure monitoring with Prometheus/Grafana
3. Set up automated backups
4. Configure log aggregation
5. Set up CI/CD pipeline for deployments

## Getting Started

### Prerequisites

- Docker & Docker Compose  
- Kubernetes cluster (for production)  
- PostgreSQL cluster or managed service for shards  

### Development Setup

1. Clone the repository:  
   ```bash
   git clone https://github.com/thorlorick/database_gradeinsight.git
   cd database_gradeinsight
