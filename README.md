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
