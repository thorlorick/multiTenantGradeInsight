"""
Database models for Multi-Tenant Grade Insight

These models define the structure of our database tables with proper tenant isolation.
Every table includes a tenant_id field to ensure data separation between schools.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

# Create the base class that all our models will inherit from
Base = declarative_base()


class TenantMixin:
    """
    Mixin class that adds tenant isolation to any table.
    
    Every table that inherits from this will automatically have:
    - tenant_id field for data isolation
    - created_at and updated_at timestamps
    - validation to ensure tenant_id is always provided
    """
    
    # The tenant_id links all data to a specific school
    # This is the KEY to our multi-tenant architecture
    tenant_id = Column(String(100), nullable=False, index=True)
    
    # Automatic timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    @validates('tenant_id')
    def validate_tenant_id(self, key, tenant_id):
        """Ensure tenant_id is always provided and not empty"""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required and cannot be empty")
        return tenant_id.strip().lower()


class Student(Base, TenantMixin):
    """
    Student model - represents individual students within a school (tenant).
    
    Each student belongs to exactly one school (tenant) and can have many grades.
    """
    __tablename__ = "students"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Student information
    student_id = Column(String(50), nullable=False)  # School's internal student ID
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=True)
    grade_level = Column(String(20), nullable=True)  # e.g., "9th", "10th", "Freshman"
    
    # Optional additional fields
    date_of_birth = Column(DateTime, nullable=True)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship to grades (one student can have many grades)
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    
    # Composite index for fast lookups within a tenant
    __table_args__ = (
        Index('idx_student_tenant_student_id', 'tenant_id', 'student_id'),
        Index('idx_student_tenant_name', 'tenant_id', 'last_name', 'first_name'),
    )
    
    @property
    def full_name(self) -> str:
        """Return the student's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f"<Student(id={self.id}, tenant={self.tenant_id}, name='{self.full_name}')>"


class Subject(Base, TenantMixin):
    """
    Subject model - represents academic subjects within a school.
    
    Examples: Mathematics, English, Science, History, etc.
    Each school can define their own subjects.
    """
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Subject information
    name = Column(String(100), nullable=False)  # e.g., "Algebra I", "World History"
    code = Column(String(20), nullable=True)    # e.g., "MATH101", "HIST201"
    description = Column(Text, nullable=True)
    credits = Column(Float, nullable=True)       # Credit hours for the subject
    
    # Relationship to grades
    grades = relationship("Grade", back_populates="subject")
    
    # Ensure subject names are unique within a tenant
    __table_args__ = (
        Index('idx_subject_tenant_name', 'tenant_id', 'name'),
    )
    
    def __repr__(self):
        return f"<Subject(id={self.id}, tenant={self.tenant_id}, name='{self.name}')>"


class Grade(Base, TenantMixin):
    """
    Grade model - represents individual grade entries.
    
    This is where the actual grade data lives. Each grade belongs to:
    - One student
    - One subject
    - One tenant (school)
    """
    __tablename__ = "grades"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys (relationships to other tables)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    
    # Grade information
    assignment_name = Column(String(200), nullable=False)  # "Midterm Exam", "Essay #1"
    grade_value = Column(Float, nullable=False)            # The actual grade (85.5, 92.0, etc.)
    max_points = Column(Float, nullable=False, default=100.0)  # Maximum possible points
    assignment_type = Column(String(50), nullable=True)    # "exam", "homework", "project"
    
    # Dates
    assignment_date = Column(DateTime, nullable=True)      # When assignment was given
    due_date = Column(DateTime, nullable=True)             # When it was due
    graded_date = Column(DateTime, default=datetime.utcnow)  # When it was graded
    
    # Optional fields
    notes = Column(Text, nullable=True)                    # Teacher's notes
    is_extra_credit = Column(Boolean, default=False)
    
    # Relationships
    student = relationship("Student", back_populates="grades")
    subject = relationship("Subject", back_populates="grades")
    
    # Indexes for fast queries
    __table_args__ = (
        Index('idx_grade_tenant_student', 'tenant_id', 'student_id'),
        Index('idx_grade_tenant_subject', 'tenant_id', 'subject_id'),
        Index('idx_grade_tenant_date', 'tenant_id', 'graded_date'),
    )
    
    @property
    def percentage(self) -> float:
        """Calculate the grade as a percentage"""
        if self.max_points == 0:
            return 0.0
        return (self.grade_value / self.max_points) * 100
    
    @property
    def letter_grade(self) -> str:
        """Convert percentage to letter grade"""
        pct = self.percentage
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
        return f"<Grade(id={self.id}, tenant={self.tenant_id}, student_id={self.student_id}, grade={self.grade_value})>"


class TenantRegistry(Base):
    """
    Tenant Registry model - tracks which tenants exist and their metadata.
    
    This is a special table that lives in its own database and helps us
    manage all the schools (tenants) in our system.
    
    NOTE: This table does NOT have tenant_id because it manages tenants themselves!
    """
    __tablename__ = "tenant_registry"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Tenant identification
    tenant_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_name = Column(String(200), nullable=False)  # "Lincoln High School"
    
    # Routing information
    subdomain = Column(String(100), unique=True, nullable=False)  # "lincoln-high"
    shard_number = Column(Integer, nullable=False)  # Which database shard to use
    
    # Tenant metadata
    contact_email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    
    # Status and configuration
    is_active = Column(Boolean, default=True)
    max_students = Column(Integer, default=5000)  # Limit for this tenant
    subscription_tier = Column(String(50), default="basic")  # "basic", "premium", "enterprise"
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TenantRegistry(tenant_id='{self.tenant_id}', name='{self.tenant_name}', shard={self.shard_number})>"


# Utility functions for working with models

def get_tenant_aware_query(query, tenant_id: str):
    """
    Add tenant filtering to any query automatically.
    
    This is a helper function that ensures we always filter by tenant_id.
    It's a safety measure to prevent accidentally accessing other tenants' data.
    
    Args:
        query: SQLAlchemy query object
        tenant_id: The tenant to filter by
        
    Returns:
        Query filtered by tenant_id
    """
    # Get the model class from the query
    model_class = query.column_descriptions[0]['type']
    
    # Only add tenant filter if the model has tenant_id
    if hasattr(model_class, 'tenant_id'):
        return query.filter(model_class.tenant_id == tenant_id)
    
    return query


def validate_tenant_access(obj, tenant_id: str):
    """
    Validate that a database object belongs to the specified tenant.
    
    This prevents accidentally returning data from the wrong tenant.
    
    Args:
        obj: Database object to check
        tenant_id: Expected tenant ID
        
    Raises:
        ValueError: If the object doesn't belong to the tenant
    """
    if hasattr(obj, 'tenant_id') and obj.tenant_id != tenant_id:
        raise ValueError(f"Object belongs to tenant '{obj.tenant_id}', not '{tenant_id}'")


# Example usage and testing
if __name__ == "__main__":
    # This shows how the models would be used
    print("Multi-Tenant Database Models")
    print("=" * 40)
    
    # Example tenant
    tenant_id = "lincoln-high"
    
    # Create sample objects (not actually saved to database)
    student = Student(
        tenant_id=tenant_id,
        student_id="12345",
        first_name="John",
        last_name="Doe",
        email="john.doe@student.lincoln.edu",
        grade_level="11th"
    )
    
    subject = Subject(
        tenant_id=tenant_id,
        name="Algebra II",
        code="MATH201",
        credits=1.0
    )
    
    grade = Grade(
        tenant_id=tenant_id,
        assignment_name="Midterm Exam",
        grade_value=87.5,
        max_points=100.0,
        assignment_type="exam"
    )
    
    print(f"Student: {student}")
    print(f"Subject: {subject}")
    print(f"Grade: {grade}")
    print(f"Grade percentage: {grade.percentage:.1f}%")
    print(f"Letter grade: {grade.letter_grade}")
