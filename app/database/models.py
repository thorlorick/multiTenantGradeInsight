"""
Simple Multi-Tenant Database Models for Grade Insight
Just the essentials: names, emails, dates, grades and total points
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class TenantRegistry(Base):
    """
    Tenant registry - maps tenants to database shards
    Used by connection.py for routing
    """
    __tablename__ = "tenant_registry"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_name = Column(String(200), nullable=False)
    subdomain = Column(String(100), unique=True, nullable=True)
    shard_number = Column(Integer, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    admin_email = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TenantRegistry(tenant_id='{self.tenant_id}', shard={self.shard_number})>"


class Student(Base):
    """
    Student model - just the basics needed for grades
    """
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Basic student info
    name = Column(String(200), nullable=False)  # Full name
    email = Column(String(200), nullable=True)  # Student email
    student_number = Column(String(50), nullable=True)  # School ID
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'student_number', name='uq_student_tenant_number'),
        Index('idx_student_tenant', 'tenant_id'),
        Index('idx_student_email', 'email'),
    )
    
    def __repr__(self):
        return f"<Student(id={self.id}, name='{self.name}')>"


class Grade(Base):
    """
    Grade model - individual grade entries with dates and points
    """
    __tablename__ = "grades"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Foreign key
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    
    # Grade info
    subject = Column(String(100), nullable=False)  # Math, English, etc.
    assignment = Column(String(200), nullable=True)  # Test 1, Homework 3, etc.
    points_earned = Column(Float, nullable=True)  # Points student earned
    points_possible = Column(Float, nullable=False)  # Total points possible
    grade_date = Column(DateTime, nullable=False)  # When grade was recorded
    
    # Optional metadata
    notes = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="grades")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_grade_tenant_student', 'tenant_id', 'student_id'),
        Index('idx_grade_tenant_subject', 'tenant_id', 'subject'),
        Index('idx_grade_date', 'grade_date'),
    )
    
    @property
    def percentage(self) -> Optional[float]:
        """Calculate grade percentage"""
        if self.points_earned is None or self.points_possible == 0:
            return None
        return (self.points_earned / self.points_possible) * 100
    
    def __repr__(self):
        return f"<Grade(id={self.id}, student_id={self.student_id}, subject='{self.subject}', points={self.points_earned}/{self.points_possible})>"


# Simple utility functions for working with grades
def calculate_total_points(grades):
    """Calculate total points from a list of grades"""
    earned = sum(g.points_earned or 0 for g in grades)
    possible = sum(g.points_possible for g in grades)
    return earned, possible


def calculate_subject_average(grades, subject):
    """Calculate average for a specific subject"""
    subject_grades = [g for g in grades if g.subject == subject]
    if not subject_grades:
        return None
    
    earned, possible = calculate_total_points(subject_grades)
    if possible == 0:
        return None
    
    return (earned / possible) * 100
