"""
Simplified Multi-Tenant Gradebook Models
Matches your CSV template: last_name, first_name, email, assignment columns

Focus: Just load marks into database with grade percentage calculation
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class TenantMixin:
    """Simple tenant isolation mixin"""
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Tenant(Base):
    """Tenant registry - each class/school"""
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)  # "Grade 10 Math" or "Springfield Elementary"
    tenant_key = Column(String(100), unique=True, nullable=False, index=True)
    admin_email = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Tenant(key='{self.tenant_key}', name='{self.name}')>"


class Student(Base, TenantMixin):
    """Students - matches your CSV: last_name, first_name, email"""
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True)
    
    # Core student info from CSV
    last_name = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)  # Unique ID as you specified
    
    # Simple flags
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationships
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_student_tenant_email'),
        Index('idx_student_tenant_active', 'tenant_id', 'is_active'),
        Index('idx_student_tenant_name', 'tenant_id', 'last_name', 'first_name'),
    )
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f"<Student(email='{self.email}', name='{self.full_name}')>"


class Assignments(Base, TenantMixin):
    """Assignments - matches your CSV columns after email"""
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True)
    
    # Assignment info from CSV headers
    name = Column(String(200), nullable=False)  # "Math Test", "Essay 1", "Science Lab"
    assignment_date = Column(DateTime, nullable=True)  # From DATE row in CSV
    total_points = Column(Float, nullable=False, default=100.0)  # From POINTS row in CSV
    
    # Simple flags
    is_active = Column(Boolean, default=True)
    
    # Relationships
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_assignment_tenant_name'),
        Index('idx_assignment_tenant_active', 'tenant_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Assignments(name='{self.name}', points={self.total_points})>"
# Add this to your app/database/models.py file

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

class TenantRegistry(Base):
    """
    Simple registry for schools using the grade management system.
    Maps school subdomains to their basic info and database shard.
    """
    __tablename__ = "tenant_registry"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # School identification
    tenant_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "lincoln-high"
    tenant_name = Column(String(200), nullable=False)  # e.g., "Lincoln High School"
    subdomain = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "lincoln-high"
    
    # Database sharding (simple)
    shard_number = Column(Integer, nullable=False, default=1)  # Which database shard
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<TenantRegistry(tenant_id='{self.tenant_id}', name='{self.tenant_name}')>"

class Grade(Base, TenantMixin):
    """Individual grades - the actual marks from CSV"""
    __tablename__ = "grades"
    
    id = Column(Integer, primary_key=True)
    
    # Foreign keys
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    
    # Grade data from CSV
    points_earned = Column(Float, nullable=True)  # The actual score from CSV
    
    # Relationships
    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignments", back_populates="grades")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'student_id', 'assignment_id', name='uq_grade_student_assignment'),
        Index('idx_grade_tenant_student', 'tenant_id', 'student_id'),
        Index('idx_grade_tenant_assignment', 'tenant_id', 'assignment_id'),
    )
    
    @property
    def percentage(self) -> Optional[float]:
        """Calculate grade percentage - the only math you need"""
        if self.points_earned is None or self.assignment.total_points == 0:
            return None
        return round((self.points_earned / self.assignment.total_points) * 100, 1)
    
    def __repr__(self):
        return f"<Grade(student_id={self.student_id}, assignment_id={self.assignment_id}, earned={self.points_earned})>"


class TenantQuery:
    """Simple tenant-aware query helper"""
    
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    def query(self, model_class):
        """Create query with tenant filtering"""
        query = self.session.query(model_class)
        if hasattr(model_class, 'tenant_id'):
            query = query.filter(model_class.tenant_id == self.tenant_id)
        return query
    
    def get_or_create_student(self, last_name: str, first_name: str, email: str) -> Student:
        """Get existing student or create new one"""
        student = self.query(Student).filter(Student.email == email).first()
        if not student:
            student = Student(
                tenant_id=self.tenant_id,
                last_name=last_name,
                first_name=first_name,
                email=email
            )
            self.session.add(student)
            self.session.flush()  # Get the ID
        return student
    
    def get_or_create_assignment(self, name: str, assignment_date: str = None, total_points: float = 100.0) -> Assignments:
        """Get existing assignment or create new one"""
        assignment = self.query(Assignments).filter(Assignments.name == name).first()
        if not assignment:
            date_obj = None
            if assignment_date and assignment_date != '-':
                try:
                    date_obj = datetime.strptime(assignment_date, '%Y-%m-%d')
                except ValueError:
                    pass
            
            assignment = Assignments(
                tenant_id=self.tenant_id,
                name=name,
                assignment_date=date_obj,
                total_points=total_points
            )
            self.session.add(assignment)
            self.session.flush()  # Get the ID
        return assignment
    
    def create_or_update_grade(self, student: Student, assignment: Assignments, points_earned: float) -> Grade:
        """Create or update a grade"""
        grade = self.query(Grade).filter(
            Grade.student_id == student.id,
            Grade.assignment_id == assignment.id
        ).first()
        
        if grade:
            grade.points_earned = points_earned
        else:
            grade = Grade(
                tenant_id=self.tenant_id,
                student_id=student.id,
                assignment_id=assignment.id,
                points_earned=points_earned
            )
            self.session.add(grade)
        
        return grade
    
    def get_all_students(self) -> List[Student]:
        """Get all active students"""
        return self.query(Student).filter(Student.is_active == True).order_by(Student.last_name, Student.first_name).all()
    
    def get_all_assignments(self) -> List[Assignments]:
        """Get all active assignments"""
        return self.query(Assignments).filter(Assignments.is_active == True).order_by(Assignments.name).all()
    
    def get_grades_for_display(self) -> dict:
        """Get all data formatted for gradebook display"""
        students = self.get_all_students()
        assignments = self.get_all_assignments()
        
        # Get all grades for this tenant
        grades = self.query(Grade).all()
        grade_lookup = {(g.student_id, g.assignment_id): g for g in grades}
        
        # Build display data
        display_data = {
            'students': [],
            'assignments': [
                {
                    'id': a.id,
                    'name': a.name,
                    'date': a.assignment_date.strftime('%Y-%m-%d') if a.assignment_date else '',
                    'total_points': a.total_points
                }
                for a in assignments
            ]
        }
        
        for student in students:
            student_data = {
                'id': student.id,
                'last_name': student.last_name,
                'first_name': student.first_name,
                'email': student.email,
                'grades': {}
            }
            
            for assignment in assignments:
                grade = grade_lookup.get((student.id, assignment.id))
                if grade:
                    student_data['grades'][assignment.id] = {
                        'points_earned': grade.points_earned,
                        'percentage': grade.percentage
                    }
                else:
                    student_data['grades'][assignment.id] = {
                        'points_earned': None,
                        'percentage': None
                    }
            
            display_data['students'].append(student_data)
        
        return display_data


def create_tenant_session(session: Session, tenant_id: uuid.UUID) -> TenantQuery:
    """Factory for tenant-aware operations"""
    return TenantQuery(session, tenant_id)


def parse_csv_and_load_grades(session: Session, tenant_id: uuid.UUID, csv_content: str) -> dict:
    """
    Parse your CSV format and load grades into database
    
    Expected format:
    last_name,first_name,email,Math Test,Essay 1,Science Lab
    DATE,-,-,2025-06-01,2025-06-03,2025-06-05
    POINTS,-,-,100,100,100
    Smith,Alice,alice.smith@example.com,85,90,78
    Johnson,Bob,bob.johnson@example.com,88,92,81
    """
    
    lines = csv_content.strip().split('\n')
    if len(lines) < 4:
        raise ValueError("CSV must have at least 4 rows: headers, dates, points, and one student")
    
    # Parse headers
    headers = [h.strip() for h in lines[0].split(',')]
    assignment_names = headers[3:]  # Skip last_name, first_name, email
    
    # Parse dates and points
    dates = [d.strip() for d in lines[1].split(',')][3:]
    points = [float(p.strip()) if p.strip() and p.strip() != '-' else 100.0 
              for p in lines[2].split(',')][3:]
    
    tenant_query = create_tenant_session(session, tenant_id)
    
    # Create assignments
    assignments = []
    for i, name in enumerate(assignment_names):
        date = dates[i] if i < len(dates) else None
        total_points = points[i] if i < len(points) else 100.0
        assignment = tenant_query.get_or_create_assignment(name, date, total_points)
        assignments.append(assignment)
    
    # Process student data
    students_processed = 0
    grades_processed = 0
    
    for line in lines[3:]:  # Skip header, date, and points rows
        if not line.strip():
            continue
            
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 3:
            continue
            
        last_name, first_name, email = parts[0], parts[1], parts[2]
        if not last_name or not first_name or not email:
            continue
            
        # Create/get student
        student = tenant_query.get_or_create_student(last_name, first_name, email)
        students_processed += 1
        
        # Process grades
        for i, assignment in enumerate(assignments):
            if i + 3 < len(parts):  # +3 to skip last_name, first_name, email
                score_str = parts[i + 3].strip()
                if score_str and score_str != '-':
                    try:
                        points_earned = float(score_str)
                        tenant_query.create_or_update_grade(student, assignment, points_earned)
                        grades_processed += 1
                    except ValueError:
                        pass  # Skip invalid scores
    
    session.commit()
    
    return {
        'assignments_created': len(assignments),
        'students_processed': students_processed,
        'grades_processed': grades_processed
    }


if __name__ == "__main__":
    print("Simplified Multi-Tenant Gradebook Models")
    print("=" * 50)
    print("✓ Matches your CSV template exactly")
    print("✓ Simple grade percentage calculation")
    print("✓ Multi-tenant support")
    print("✓ CSV parsing and loading built-in")
    print("✓ No unnecessary complexity")
