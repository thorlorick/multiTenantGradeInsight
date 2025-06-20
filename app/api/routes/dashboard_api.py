"""
Dashboard API Routes

These endpoints provide data for the dashboard frontend.
All endpoints are multi-tenant aware and automatically filter data by tenant.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, and_, or_
from datetime import datetime, timedelta

from app.database.connection import get_tenant_db_session
from app.database.models import Student, Assignment, Grade
from app.middleware.tenant import get_current_tenant_id


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def validate_tenant_access(session: Session, tenant_id: str) -> bool:
    """
    Validate that the current tenant_id is valid and accessible.
    This should be expanded based on your tenant validation logic.
    """
    # Add your tenant validation logic here
    # For example, check if tenant exists in a tenants table
    return tenant_id is not None and len(tenant_id.strip()) > 0


async def ensure_tenant_resource_access(
    session: Session, 
    model_class, 
    resource_id: int, 
    tenant_id: str
):
    """
    Ensure a resource exists and belongs to the current tenant.
    """
    query = select(model_class).where(
        model_class.id == resource_id,
        model_class.tenant_id == tenant_id
    )
    
    # Add is_active check if the model has it
    if hasattr(model_class, 'is_active'):
        query = query.where(model_class.is_active == True)
    
    result = await session.execute(query)
    resource = result.scalar_one_or_none()
    
    if not resource:
        raise HTTPException(
            status_code=404, 
            detail=f"{model_class.__name__} not found or access denied"
        )
    
    return resource


@router.get("/grades")
async def get_grades_data(
    tenant_id: str = Depends(get_current_tenant_id),
    student_search: Optional[str] = None,
    assignment_search: Optional[str] = None
):
    """
    Get all grades data for the dashboard table.
    
    This endpoint returns the data structure needed for the dashboard:
    - Students as rows
    - Assignments as columns
    - Grades as cell values
    """
    
    async with get_tenant_db_session(tenant_id) as session:
        # Build base query
        query = select(
            Student.id.label('student_id'),
            Student.first_name,
            Student.last_name,
            Student.email,
            Student.grade_level,
            Assignment.id.label('assignment_id'),
            Assignment.assignment_name,
            Assignment.assignment_type,
            Assignment.subject,
            Assignment.max_points,
            Grade.points_earned,
            Grade.points_possible,
            Grade.percentage,
            Grade.letter_grade,
            Grade.created_at.label('grade_created_at')
        ).select_from(
            Student.__table__.outerjoin(Grade.__table__)
            .outerjoin(Assignment.__table__)
        ).where(
            Student.tenant_id == tenant_id,
            Student.is_active == True,
            # Ensure grades and assignments also belong to the same tenant
            (Grade.tenant_id == tenant_id) | (Grade.tenant_id.is_(None)),
            (Assignment.tenant_id == tenant_id) | (Assignment.tenant_id.is_(None))
        )
        
        # Apply search filters
        if student_search:
            search_term = f"%{student_search.lower()}%"
            query = query.where(
                func.lower(Student.first_name).like(search_term) |
                func.lower(Student.last_name).like(search_term) |
                func.lower(Student.email).like(search_term)
            )
        
        if assignment_search:
            search_term = f"%{assignment_search.lower()}%"
            query = query.where(
                func.lower(Assignment.assignment_name).like(search_term) |
                func.lower(Assignment.assignment_type).like(search_term) |
                func.lower(Assignment.subject).like(search_term)
            )
        
        # Execute query
        result = await session.execute(query)
        rows = result.fetchall()
        
        # Process results into dashboard format
        students_dict = {}
        assignments_dict = {}
        
        for row in rows:
            # Build student record
            student_key = row.student_id
            if student_key not in students_dict:
                students_dict[student_key] = {
                    'id': row.student_id,
                    'name': f"{row.first_name} {row.last_name}",
                    'email': row.email,
                    'grade_level': row.grade_level,
                    'grades': {}
                }
            
            # Build assignment record
            if row.assignment_id:
                assignment_key = row.assignment_id
                if assignment_key not in assignments_dict:
                    assignments_dict[assignment_key] = {
                        'id': row.assignment_id,
                        'name': row.assignment_name,
                        'type': row.assignment_type,
                        'subject': row.subject,
                        'max_points': row.max_points
                    }
                
                # Add grade to student
                if row.points_earned is not None:
                    students_dict[student_key]['grades'][assignment_key] = {
                        'points_earned': row.points_earned,
                        'points_possible': row.points_possible,
                        'percentage': row.percentage,
                        'letter_grade': row.letter_grade,
                        'created_at': row.grade_created_at.isoformat() if row.grade_created_at else None
                    }
        
        return {
            'students': list(students_dict.values()),
            'assignments': list(assignments_dict.values()),
            'total_students': len(students_dict),
            'total_assignments': len(assignments_dict)
        }


@router.get("/stats")
async def get_dashboard_stats(
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get summary statistics for the dashboard.
    """
    
    async with get_tenant_db_session(tenant_id) as session:
        # Get basic counts
        student_count_query = select(func.count(Student.id)).where(
            Student.tenant_id == tenant_id,
            Student.is_active == True
        )
        student_count = await session.execute(student_count_query)
        total_students = student_count.scalar()
        
        assignment_count_query = select(func.count(Assignment.id)).where(
            Assignment.tenant_id == tenant_id,
            Assignment.is_active == True
        )
        assignment_count = await session.execute(assignment_count_query)
        total_assignments = assignment_count.scalar()
        
        grade_count_query = select(func.count(Grade.id)).where(
            Grade.tenant_id == tenant_id
        )
        grade_count = await session.execute(grade_count_query)
        total_grades = grade_count.scalar()
        
        # Get average grade
        avg_grade_query = select(func.avg(Grade.percentage)).where(
            Grade.tenant_id == tenant_id,
            Grade.percentage.isnot(None)
        )
        avg_grade_result = await session.execute(avg_grade_query)
        avg_grade = avg_grade_result.scalar()
        
        # Get grade distribution
        grade_distribution_query = select(
            func.count(Grade.id).label('count'),
            func.case(
                (Grade.percentage >= 90, 'A'),
                (Grade.percentage >= 80, 'B'),
                (Grade.percentage >= 70, 'C'),
                (Grade.percentage >= 60, 'D'),
                else_='F'
            ).label('letter_grade')
        ).where(
            Grade.tenant_id == tenant_id,
            Grade.percentage.isnot(None)
        ).group_by('letter_grade')
        
        distribution_result = await session.execute(grade_distribution_query)
        grade_distribution = {row.letter_grade: row.count for row in distribution_result}
        
        # Get recent activity (last 10 grades)
        recent_grades_query = select(
            Grade.points_earned,
            Grade.points_possible,
            Grade.percentage,
            Grade.created_at,
            Student.first_name,
            Student.last_name,
            Assignment.assignment_name
        ).select_from(
            Grade.__table__.join(Student.__table__).join(Assignment.__table__)
        ).where(
            Grade.tenant_id == tenant_id
        ).order_by(desc(Grade.created_at)).limit(10)
        
        recent_result = await session.execute(recent_grades_query)
        recent_grades = [
            {
                'student_name': f"{row.first_name} {row.last_name}",
                'assignment_name': row.assignment_name,
                'points_earned': row.points_earned,
                'points_possible': row.points_possible,
                'percentage': row.percentage,
                'created_at': row.created_at.isoformat() if row.created_at else None
            }
            for row in recent_result
        ]
        
        return {
            'total_students': total_students,
            'total_assignments': total_assignments,
            'total_grades': total_grades,
            'average_grade': round(avg_grade, 2) if avg_grade else None,
            'grade_distribution': grade_distribution,
            'recent_grades': recent_grades
        }


@router.get("/assignments")
async def get_assignments(
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get all assignments for the current tenant.
    """
    
    async with get_tenant_db_session(tenant_id) as session:
        query = select(Assignment).where(
            Assignment.tenant_id == tenant_id,
            Assignment.is_active == True
        ).order_by(Assignment.assignment_name)
        
        result = await session.execute(query)
        assignments = result.scalars().all()
        
        return [
            {
                'id': assignment.id,
                'name': assignment.assignment_name,
                'type': assignment.assignment_type,
                'subject': assignment.subject,
                'max_points': assignment.max_points,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                'created_at': assignment.created_at.isoformat() if assignment.created_at else None
            }
            for assignment in assignments
        ]


@router.get("/students")
async def get_students(
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get all students for the current tenant.
    """
    
    async with get_tenant_db_session(tenant_id) as session:
        query = select(Student).where(
            Student.tenant_id == tenant_id,
            Student.is_active == True
        ).order_by(Student.last_name, Student.first_name)
        
        result = await session.execute(query)
        students = result.scalars().all()
        
        return [
            {
                'id': student.id,
                'student_id': student.student_id,
                'name': student.full_name,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'email': student.email,
                'grade_level': student.grade_level,
                'created_at': student.created_at.isoformat() if student.created_at else None
            }
            for student in students
        ]


@router.get("/downloadTemplate")
async def download_csv_template():
    """
    Download CSV template for grade uploads.
    """
    from fastapi.responses import Response
    
    # CSV template content
    csv_content = """student_id,first_name,last_name,email,assignment_name,assignment_type,subject,points_earned,points_possible,due_date
STU001,John,Doe,john.doe@student.school.edu,Math Quiz 1,quiz,Mathematics,85,100,2024-01-15
STU002,Jane,Smith,jane.smith@student.school.edu,Math Quiz 1,quiz,Mathematics,92,100,2024-01-15
STU001,John,Doe,john.doe@student.school.edu,English Essay,essay,English,78,100,2024-01-20
STU002,Jane,Smith,jane.smith@student.school.edu,English Essay,essay,English,88,100,2024-01-20"""
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grade_template.csv"}
    )


@router.get("/search")
async def search_grades(
    tenant_id: str = Depends(get_current_tenant_id),
    q: Optional[str] = None,
    type: Optional[str] = None  # 'student' or 'assignment'
):
    """
    Search for students or assignments.
    """
    
    if not q:
        return {'results': []}
    
    async with get_tenant_db_session(tenant_id) as session:
        search_term = f"%{q.lower()}%"
        
        if type == 'student':
            query = select(Student).where(
                Student.tenant_id == tenant_id,
                Student.is_active == True,
                (func.lower(Student.first_name).like(search_term) |
                 func.lower(Student.last_name).like(search_term) |
                 func.lower(Student.email).like(search_term))
            ).limit(10)
            
            result = await session.execute(query)
            students = result.scalars().all()
            
            return {
                'results': [
                    {
                        'id': student.id,
                        'name': student.full_name,
                        'email': student.email,
                        'type': 'student'
                    }
                    for student in students
                ]
            }
        
        elif type == 'assignment':
            query = select(Assignment).where(
                Assignment.tenant_id == tenant_id,
                Assignment.is_active == True,
                (func.lower(Assignment.assignment_name).like(search_term) |
                 func.lower(Assignment.assignment_type).like(search_term) |
                 func.lower(Assignment.subject).like(search_term))
            ).limit(10)
            
            result = await session.execute(query)
            assignments = result.scalars().all()
            
            return {
                'results': [
                    {
                        'id': assignment.id,
                        'name': assignment.assignment_name,
                        'type': assignment.assignment_type,
                        'subject': assignment.subject,
                        'assignment_type': 'assignment'
                    }
                    for assignment in assignments
                ]
            }
        
        else:
            # Search both students and assignments
            student_query = select(Student).where(
                Student.tenant_id == tenant_id,
                Student.is_active == True,
                (func.lower(Student.first_name).like(search_term) |
                 func.lower(Student.last_name).like(search_term) |
                 func.lower(Student.email).like(search_term))
            ).limit(5)
            
            assignment_query = select(Assignment).where(
                Assignment.tenant_id == tenant_id,
                Assignment.is_active == True,
                (func.lower(Assignment.assignment_name).like(search_term) |
                 func.lower(Assignment.assignment_type).like(search_term) |
                 func.lower(Assignment.subject).like(search_term))
            ).limit(5)
            
            student_result = await session.execute(student_query)
            assignment_result = await session.execute(assignment_query)
            
            students = student_result.scalars().all()
            assignments = assignment_result.scalars().all()
            
            results = []
            
            # Add student results
            for student in students:
                results.append({
                    'id': student.id,
                    'name': student.full_name,
                    'email': student.email,
                    'type': 'student'
                })
            
            # Add assignment results
            for assignment in assignments:
                results.append({
                    'id': assignment.id,
                    'name': assignment.assignment_name,
                    'type': assignment.assignment_type,
                    'subject': assignment.subject,
                    'assignment_type': 'assignment'
                })
            
            return {'results': results}


@router.get("/student/{student_id}/grades")
async def get_student_grades(
    student_id: int,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get all grades for a specific student.
    """
    
    async with get_tenant_db_session(tenant_id) as session:
        # Verify student exists and belongs to tenant
        student = await ensure_tenant_resource_access(
            session, Student, student_id, tenant_id
        )
        
        # Get grades for student
        grades_query = select(
            Grade.id,
            Grade.points_earned,
            Grade.points_possible,
            Grade.percentage,
            Grade.letter_grade,
            Grade.created_at,
            Assignment.assignment_name,
            Assignment.assignment_type,
            Assignment.subject,
            Assignment.max_points,
            Assignment.due_date
        ).select_from(
            Grade.__table__.join(Assignment.__table__)
        ).where(
            Grade.student_id == student_id,
            Grade.tenant_id == tenant_id
        ).order_by(desc(Grade.created_at))
        
        grades_result = await session.execute(grades_query)
        grades = grades_result.fetchall()
        
        return {
            'student': {
                'id': student.id,
                'name': student.full_name,
                'email': student.email,
                'grade_level': student.grade_level
            },
            'grades': [
                {
                    'id': grade.id,
                    'points_earned': grade.points_earned,
                    'points_possible': grade.points_possible,
                    'percentage': grade.percentage,
                    'letter_grade': grade.letter_grade,
                    'created_at': grade.created_at.isoformat() if grade.created_at else None,
                    'assignment': {
                        'name': grade.assignment_name,
                        'type': grade.assignment_type,
                        'subject': grade.subject,
                        'max_points': grade.max_points,
                        'due_date': grade.due_date.isoformat() if grade.due_date else None
                    }
                }
                for grade in grades
            ]
        }


@router.get("/assignment/{assignment_id}/grades")
async def get_assignment_grades(
    assignment_id: int,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get all grades for a specific assignment.
    """
    
    async with get_tenant_db_session(tenant_id) as session:
        # Verify assignment exists and belongs to tenant
        assignment = await ensure_tenant_resource_access(
            session, Assignment, assignment_id, tenant_id
        )
        
        # Get grades for assignment
        grades_query = select(
            Grade.id,
            Grade.points_earned,
            Grade.points_possible,
            Grade.percentage,
            Grade.letter_grade,
            Grade.created_at,
            Student.first_name,
            Student.last_name,
            Student.email,
            Student.grade_level
        ).select_from(
            Grade.__table__.join(Student.__table__)
        ).where(
            Grade.assignment_id == assignment_id,
            Grade.tenant_id == tenant_id
        ).order_by(Student.last_name, Student.first_name)
        
        grades_result = await session.execute(grades_query)
        grades = grades_result.fetchall()
        
        # Calculate assignment statistics
        total_grades = len(grades)
        if total_grades > 0:
            percentages = [g.percentage for g in grades if g.percentage is not None]
            avg_percentage = sum(percentages) / len(percentages) if percentages else None
            highest_percentage = max(percentages) if percentages else None
            lowest_percentage = min(percentages) if percentages else None
        else:
            avg_percentage = highest_percentage = lowest_percentage = None
        
        return {
            'assignment': {
                'id': assignment.id,
                'name': assignment.assignment_name,
                'type': assignment.assignment_type,
                'subject': assignment.subject,
                'max_points': assignment.max_points,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None
            },
            'statistics': {
                'total_submissions': total_grades,
                'average_percentage': round(avg_percentage, 2) if avg_percentage else None,
                'highest_percentage': highest_percentage,
                'lowest_percentage': lowest_percentage
            },
            'grades': [
                {
                    'id': grade.id,
                    'points_earned': grade.points_earned,
                    'points_possible': grade.points_possible,
                    'percentage': grade.percentage,
                    'letter_grade': grade.letter_grade,
                    'created_at': grade.created_at.isoformat() if grade.created_at else None,
                    'student': {
                        'name': f"{grade.first_name} {grade.last_name}",
                        'email': grade.email,
                        'grade_level': grade.grade_level
                    }
                }
                for grade in grades
            ]
        }
