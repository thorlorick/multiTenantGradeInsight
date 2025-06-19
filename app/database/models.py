"""
Scalable Multi-Tenant Database Models
Optimized for 10 tenants now, 100 tenants later

Key design decisions for this scale:
- Simple integer PKs for performance
- UUID tenant_id for security and uniqueness
- Strategic indexing for fast queries
- Row-level security patterns
- Operational simplicity for debugging/maintenance
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates, Session
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class TenantMixin:
    """
    Mixin for tenant isolation - optimized for 10-100 tenant scale
    
    Uses UUID for tenant_id (better for 100+ tenants) but keeps simple integer PKs
    for performance and operational simplicity.
    """
    
    # UUID tenant_id - scales better than strings, more secure
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Automatic timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    @validates('tenant_id')
    def validate_tenant_id(self, key, tenant_id):
        """Ensure tenant_id is always provided"""
        if not tenant_id:
            raise ValueError("tenant_id is required")
        return tenant_id


class Tenant(Base):
    """
    Tenant registry - central source of truth for all tenants
    
    At 100 tenants, you'll want good metadata here for routing,
    sharding decisions, and operational management.
    """
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Tenant identification
    tenant_key = Column(String(100), unique=True, nullable=False, index=True)  # human-readable ID
    name = Column(String(200), nullable=False)
    subdomain = Column(String(100), unique=True, nullable=True)  # optional subdomain routing
    
    # Operational metadata (crucial at 100 tenant scale)
    status = Column(String(20), default='active', index=True)  # active, suspended, trial
    tier = Column(String(20), default='standard')  # standard, premium, enterprise
    max_students = Column(Integer, default=1000)
    max_storage_mb = Column(Integer, default=1000)
    
    # Contact and billing
    admin_email = Column(String(200), nullable=False)
    billing_email = Column(String(200), nullable=True)
    
    # Sharding info (for future horizontal scaling)
    shard_key = Column(String(50), nullable=True)  # which database shard
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Tenant(key='{self.tenant_key}', name='{self.name}', status='{self.status}')>"


class Student(Base, TenantMixin):
    """
    Student model optimized for performance at scale
    
    Design decisions:
    - Simple integer PK for fast JOINs
    - Composite unique constraint on (tenant_id, student_number) for business logic
    - Strategic indexes for common query patterns
    """
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Student identification
    student_number = Column(String(50), nullable=False)  # School's student ID
    email = Column(String(200), nullable=True)  # Not required (some schools don't have student emails)
    
    # Basic info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    grade_level = Column(String(20), nullable=True)  # "9", "10", "11", "12", "K", "1st", etc.
    
    # Optional fields
    date_of_birth = Column(DateTime, nullable=True)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    graduation_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Parent/guardian info (helpful for notifications)
    parent_email = Column(String(200), nullable=True)
    parent_phone = Column(String(20), nullable=True)
    
    # Relationships
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    
    # Constraints and indexes optimized for 100-tenant scale
    __table_args__ = (
        # Business rule: student numbers must be unique within tenant
        UniqueConstraint('tenant_id', 'student_number', name='uq_student_tenant_number'),
        
        # Performance indexes for common queries
        Index('idx_student_tenant_active', 'tenant_id', 'is_active'),
        Index('idx_student_tenant_grade', 'tenant_id', 'grade_level'),
        Index('idx_student_tenant_name', 'tenant_id', 'last_name', 'first_name'),
        Index('idx_student_email', 'email'),  # for login lookups
    )
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f"<Student(id={self.id}, tenant={self.tenant_id}, number='{self.student_number}', name='{self.full_name}')>"


class Subject(Base, TenantMixin):
    """
    Subject/Course model
    
    At 100 tenants, you might want to consider a "standard subjects" catalog
    to reduce duplication, but keeping it simple for now.
    """
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Subject info
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=True)  # MATH101, ENG201, etc.
    description = Column(Text, nullable=True)
    credits = Column(Float, nullable=True)
    department = Column(String(50), nullable=True)  # Math, Science, English, etc.
    
    # Academic info
    grade_levels = Column(String(100), nullable=True)  # "9,10,11,12" or "K,1,2,3"
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationships
    grades = relationship("Grade", back_populates="subject")
    
    __table_args__ = (
        # Subject names should be unique within tenant
        UniqueConstraint('tenant_id', 'name', name='uq_subject_tenant_name'),
        Index('idx_subject_tenant_active', 'tenant_id', 'is_active'),
        Index('idx_subject_tenant_dept', 'tenant_id', 'department'),
    )
    
    def __repr__(self):
        return f"<Subject(id={self.id}, tenant={self.tenant_id}, name='{self.name}')>"


class Assignment(Base, TenantMixin):
    """
    Assignment model - represents gradeable work
    
    Separated from Grade to handle the case where assignments exist
    but not all students have grades yet.
    """
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    
    # Assignment info
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    assignment_type = Column(String(50), nullable=True)  # "exam", "homework", "project", "quiz"
    
    # Scoring
    max_points = Column(Float, nullable=False, default=100.0)
    weight = Column(Float, nullable=True, default=1.0)  # for weighted grades
    
    # Dates
    assigned_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    
    # Flags
    is_extra_credit = Column(Boolean, default=False)
    is_published = Column(Boolean, default=True)  # hidden assignments
    
    # Relationships
    subject = relationship("Subject")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_assignment_tenant_subject', 'tenant_id', 'subject_id'),
        Index('idx_assignment_tenant_due', 'tenant_id', 'due_date'),
        Index('idx_assignment_tenant_type', 'tenant_id', 'assignment_type'),
    )
    
    def __repr__(self):
        return f"<Assignment(id={self.id}, tenant={self.tenant_id}, name='{self.name}')>"


class Grade(Base, TenantMixin):
    """
    Individual grade entries
    
    This is your high-volume table - optimize indexes carefully.
    At 100 tenants with 1000 students each, this could be millions of rows.
    """
    __tablename__ = "grades"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    
    # Grade data
    points_earned = Column(Float, nullable=True)  # null = not graded yet
    points_possible = Column(Float, nullable=False)  # copied from assignment for historical accuracy
    
    # Metadata
    graded_by = Column(String(200), nullable=True)  # teacher email/name
    graded_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Flags
    is_late = Column(Boolean, default=False)
    is_excused = Column(Boolean, default=False)
    is_extra_credit = Column(Boolean, default=False)
    
    # Relationships
    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")
    
    # Critical indexes for performance at scale
    __table_args__ = (
        # Unique constraint: one grade per student per assignment
        UniqueConstraint('tenant_id', 'student_id', 'assignment_id', name='uq_grade_student_assignment'),
        
        # Performance indexes for common queries
        Index('idx_grade_tenant_student', 'tenant_id', 'student_id'),
        Index('idx_grade_tenant_assignment', 'tenant_id', 'assignment_id'),
        Index('idx_grade_tenant_graded', 'tenant_id', 'graded_at'),
        
        # Composite index for gradebook queries
        Index('idx_grade_student_assignment', 'student_id', 'assignment_id'),
    )
    
    @property
    def percentage(self) -> Optional[float]:
        """Calculate grade percentage"""
        if self.points_earned is None or self.points_possible == 0:
            return None
        return (self.points_earned / self.points_possible) * 100
    
    @property
    def letter_grade(self) -> Optional[str]:
        """Convert to letter grade"""
        pct = self.percentage
        if pct is None:
            return None
        
        if pct >= 97: return "A+"
        elif pct >= 93: return "A"
        elif pct >= 90: return "A-"
        elif pct >= 87: return "B+"
        elif pct >= 83: return "B"
        elif pct >= 80: return "B-"
        elif pct >= 77: return "C+"
        elif pct >= 73: return "C"
        elif pct >= 70: return "C-"
        elif pct >= 67: return "D+"
        elif pct >= 63: return "D"
        elif pct >= 60: return "D-"
        else: return "F"
    
    def __repr__(self):
        return f"<Grade(id={self.id}, student_id={self.student_id}, assignment_id={self.assignment_id}, earned={self.points_earned})>"


# Tenant-aware utilities for safe operations

class TenantAwareQuery:
    """
    Query helper that automatically adds tenant filtering
    
    Critical for preventing cross-tenant data leaks at scale
    """
    
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    def query(self, model_class):
        """Create a query with automatic tenant filtering"""
        query = self.session.query(model_class)
        if hasattr(model_class, 'tenant_id'):
            query = query.filter(model_class.tenant_id == self.tenant_id)
        return query
    
    def get_student(self, student_id: int) -> Optional[Student]:
        """Get student by ID within tenant"""
        return self.query(Student).filter(Student.id == student_id).first()
    
    def get_student_by_number(self, student_number: str) -> Optional[Student]:
        """Get student by school ID within tenant"""
        return self.query(Student).filter(Student.student_number == student_number).first()
    
    def get_active_students(self) -> List[Student]:
        """Get all active students in tenant"""
        return self.query(Student).filter(Student.is_active == True).all()
    
    def get_grades_for_student(self, student_id: int) -> List[Grade]:
        """Get all grades for a student"""
        return self.query(Grade).filter(Grade.student_id == student_id).all()


def validate_tenant_access(obj, expected_tenant_id: uuid.UUID):
    """
    Validate that an object belongs to the expected tenant
    
    Critical safety check - always call this before returning data
    """
    if hasattr(obj, 'tenant_id') and obj.tenant_id != expected_tenant_id:
        raise ValueError(f"Cross-tenant access violation: object belongs to {obj.tenant_id}, expected {expected_tenant_id}")


def create_tenant_aware_session(session: Session, tenant_id: uuid.UUID) -> TenantAwareQuery:
    """
    Factory function to create tenant-aware query helper
    
    Use this in your API endpoints to ensure tenant isolation
    """
    return TenantAwareQuery(session, tenant_id)


# Performance monitoring helpers for 100-tenant scale

class TenantMetrics:
    """
    Helper class for monitoring tenant resource usage
    
    Important at 100-tenant scale for identifying problematic tenants
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_tenant_stats(self, tenant_id: uuid.UUID) -> dict:
        """Get basic usage stats for a tenant"""
        return {
            'students': self.session.query(Student).filter(Student.tenant_id == tenant_id).count(),
            'subjects': self.session.query(Subject).filter(Subject.tenant_id == tenant_id).count(),
            'assignments': self.session.query(Assignment).filter(Assignment.tenant_id == tenant_id).count(),
            'grades': self.session.query(Grade).filter(Grade.tenant_id == tenant_id).count(),
        }
    
    def get_largest_tenants(self, limit: int = 10) -> List[dict]:
        """Find tenants with most data (for capacity planning)"""
        # This would need a more complex query in practice
        pass


# Example usage patterns for this scale

if __name__ == "__main__":
    print("Multi-Tenant Models - Optimized for 10→100 tenants")
    print("="*50)
    
    # Example: Safe tenant-aware operations
    tenant_id = uuid.uuid4()
    
    # This is how you'd use it in your API endpoints
    # session = get_db_session()
    # tenant_query = create_tenant_aware_session(session, tenant_id)
    # 
    # # Safe operations - automatically tenant-filtered
    # students = tenant_query.get_active_students()
    # student = tenant_query.get_student_by_number("12345")
    
    print("✓ Models optimized for operational simplicity")
    print("✓ Strategic indexing for performance")
    print("✓ Tenant-aware query helpers for safety")
    print("✓ UUID tenant IDs for security")
    print("✓ Monitoring hooks for scale management")
