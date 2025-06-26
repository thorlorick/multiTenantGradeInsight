from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case
from datetime import datetime

from app.database.connection import get_tenant_db_session
from app.database.models import Student, Assignment, Grade, Subject
from app.middleware.tenant import get_current_tenant_id

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def ensure_tenant_resource_access(
    session: Session, model_class, resource_id: int, tenant_id: str
):
    """
    Ensure a resource exists and belongs to the current tenant.
    """
    query = select(model_class).where(
        model_class.id == resource_id,
        model_class.tenant_id == tenant_id
    )
    if hasattr(model_class, 'is_active'):
        query = query.where(model_class.is_active.is_(True))

    result = await session.execute(query)
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(404, detail=f"{model_class.__name__} not found or access denied")

    return resource


@router.get("/grades")
async def get_grades_data(
    tenant_id: str = Depends(get_current_tenant_id),
    student_search: Optional[str] = None,
    assignment_search: Optional[str] = None,
):
    async with get_tenant_db_session(tenant_id) as session:
        query = select(
            Student.id.label('student_id'),
            Student.first_name,
            Student.last_name,
            Student.email,
            Student.grade_level,
            Assignment.id.label('assignment_id'),
            Assignment.name.label('assignment_name'),
            Assignment.assignment_type,
            Assignment.max_points,
            Grade.points_earned,
            Grade.points_possible,
            Grade.created_at.label('grade_created_at')
        ).select_from(
            Student.__table__.outerjoin(Grade.__table__).outerjoin(Assignment.__table__)
        ).where(
            Student.tenant_id == tenant_id,
            Student.is_active.is_(True),
            (Grade.tenant_id == tenant_id) | (Grade.tenant_id.is_(None)),
            (Assignment.tenant_id == tenant_id) | (Assignment.tenant_id.is_(None))
        )

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
                func.lower(Assignment.name).like(search_term) |
                func.lower(Assignment.assignment_type).like(search_term)
            )

        result = await session.execute(query)
        rows = result.fetchall()

        students_dict = {}
        assignments_dict = {}

        for row in rows:
            student_key = row.student_id
            if student_key not in students_dict:
                students_dict[student_key] = {
                    'id': row.student_id,
                    'name': f"{row.first_name} {row.last_name}",
                    'email': row.email,
                    'grade_level': row.grade_level,
                    'grades': {}
                }
            if row.assignment_id:
                assignment_key = row.assignment_id
                if assignment_key not in assignments_dict:
                    assignments_dict[assignment_key] = {
                        'id': row.assignment_id,
                        'name': row.assignment_name,
                        'type': row.assignment_type,
                        'max_points': row.max_points
                    }
                if row.points_earned is not None:
                    # Calculate percentage and letter grade
                    percentage = (row.points_earned / row.points_possible) * 100 if row.points_possible > 0 else 0
                    if percentage >= 90: letter_grade = "A"
                    elif percentage >= 80: letter_grade = "B"
                    elif percentage >= 70: letter_grade = "C"
                    elif percentage >= 60: letter_grade = "D"
                    else: letter_grade = "F"
                    
                    students_dict[student_key]['grades'][assignment_key] = {
                        'points_earned': row.points_earned,
                        'points_possible': row.points_possible,
                        'percentage': round(percentage, 2),
                        'letter_grade': letter_grade,
                        'created_at': row.grade_created_at.isoformat() if row.grade_created_at else None
                    }

        return {
            'students': list(students_dict.values()),
            'assignments': list(assignments_dict.values()),
            'total_students': len(students_dict),
            'total_assignments': len(assignments_dict)
        }


@router.get("/stats")
async def get_dashboard_stats(tenant_id: str = Depends(get_current_tenant_id)):
    async with get_tenant_db_session(tenant_id) as session:
        total_students = (await session.execute(
            select(func.count(Student.id)).where(
                Student.tenant_id == tenant_id, Student.is_active.is_(True)
            )
        )).scalar()

        total_assignments = (await session.execute(
            select(func.count(Assignment.id)).where(
                Assignment.tenant_id == tenant_id
            )
        )).scalar()

        total_grades = (await session.execute(
            select(func.count(Grade.id)).where(Grade.tenant_id == tenant_id)
        )).scalar()

        # Calculate average grade from points
        grade_data = (await session.execute(
            select(Grade.points_earned, Grade.points_possible).where(
                Grade.tenant_id == tenant_id, 
                Grade.points_earned.isnot(None),
                Grade.points_possible > 0
            )
        )).fetchall()
        
        if grade_data:
            percentages = [(g.points_earned / g.points_possible) * 100 for g in grade_data]
            avg_grade = sum(percentages) / len(percentages)
        else:
            avg_grade = None

        # Grade distribution
        grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        for pct in (percentages if grade_data else []):
            if pct >= 90: grade_distribution['A'] += 1
            elif pct >= 80: grade_distribution['B'] += 1
            elif pct >= 70: grade_distribution['C'] += 1
            elif pct >= 60: grade_distribution['D'] += 1
            else: grade_distribution['F'] += 1

        # Recent grades
        recent_grades_query = select(
            Grade.points_earned,
            Grade.points_possible,
            Grade.created_at,
            Student.first_name,
            Student.last_name,
            Assignment.name
        ).select_from(
            Grade.__table__.join(Student.__table__).join(Assignment.__table__)
        ).where(
            Grade.tenant_id == tenant_id
        ).order_by(desc(Grade.created_at)).limit(10)

        recent_result = await session.execute(recent_grades_query)
        recent_grades = []
        for row in recent_result:
            percentage = (row.points_earned / row.points_possible) * 100 if row.points_possible > 0 else 0
            recent_grades.append({
                'student_name': f"{row.first_name} {row.last_name}",
                'assignment_name': row.name,
                'points_earned': row.points_earned,
                'points_possible': row.points_possible,
                'percentage': round(percentage, 2),
                'created_at': row.created_at.isoformat() if row.created_at else None
            })

        return {
            'total_students': total_students,
            'total_assignments': total_assignments,
            'total_grades': total_grades,
            'average_grade': round(avg_grade, 2) if avg_grade else None,
            'grade_distribution': grade_distribution,
            'recent_grades': recent_grades
        }


@router.get("/assignments")
async def get_assignments(tenant_id: str = Depends(get_current_tenant_id)):
    async with get_tenant_db_session(tenant_id) as session:
        result = await session.execute(
            select(Assignment).where(
                Assignment.tenant_id == tenant_id
            ).order_by(Assignment.name)
        )
        assignments = result.scalars().all()

        return [
            {
                'id': a.id,
                'name': a.name,
                'type': a.assignment_type,
                'max_points': a.max_points,
                'due_date': a.due_date.isoformat() if a.due_date else None,
                'created_at': a.created_at.isoformat() if a.created_at else None
            }
            for a in assignments
        ]


@router.get("/students")
async def get_students(tenant_id: str = Depends(get_current_tenant_id)):
    async with get_tenant_db_session(tenant_id) as session:
        result = await session.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.is_active.is_(True)
            ).order_by(Student.last_name, Student.first_name)
        )
        students = result.scalars().all()

        return [
            {
                'id': s.id,
                'student_number': s.student_number,
                'name': s.full_name,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'email': s.email,
                'grade_level': s.grade_level,
                'created_at': s.created_at.isoformat() if s.created_at else None
            }
            for s in students
        ]


@router.get("/downloadTemplate")
async def download_csv_template():
    from fastapi.responses import Response
    csv_content = (
        "student_number,first_name,last_name,email,assignment_name,assignment_type,points_earned,points_possible,due_date\n"
        "STU001,John,Doe,john.doe@student.school.edu,Math Quiz 1,quiz,85,100,2024-01-15\n"
        "STU002,Jane,Smith,jane.smith@student.school.edu,Math Quiz 1,quiz,92,100,2024-01-15\n"
        "STU001,John,Doe,john.doe@student.school.edu,English Essay,essay,78,100,2024-01-20\n"
        "STU002,Jane,Smith,jane.smith@student.school.edu,English Essay,essay,88,100,2024-01-20"
    )
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
    if not q:
        return {'results': []}

    async with get_tenant_db_session(tenant_id) as session:
        search_term = f"%{q.lower()}%"

        if type == 'student':
            result = await session.execute(
                select(Student).where(
                    Student.tenant_id == tenant_id,
                    Student.is_active.is_(True),
                    (func.lower(Student.first_name).like(search_term) |
                     func.lower(Student.last_name).like(search_term) |
                     func.lower(Student.email).like(search_term))
                ).limit(10)
            )
            students = result.scalars().all()
            return {
                'results': [
                    {'id': s.id, 'name': s.full_name, 'email': s.email, 'type': 'student'}
                    for s in students
                ]
            }

        elif type == 'assignment':
            result = await session.execute(
                select(Assignment).where(
                    Assignment.tenant_id == tenant_id,
                    (func.lower(Assignment.name).like(search_term) |
                     func.lower(Assignment.assignment_type).like(search_term))
                ).limit(10)
            )
            assignments = result.scalars().all()
            return {
                'results': [
                    {
                        'id': a.id,
                        'name': a.name,
                        'type': a.assignment_type,
                        'assignment_type': 'assignment'
                    }
                    for a in assignments
                ]
            }

        else:
            # Search both students and assignments
            student_query = select(Student).where(
                Student.tenant_id == tenant_id,
                Student.is_active.is_(True),
                (func.lower(Student.first_name).like(search_term) |
                 func.lower(Student.last_name).like(search_term) |
                 func.lower(Student.email).like(search_term))
            ).limit(5)
            
            assignment_query = select(Assignment).where(
                Assignment.tenant_id == tenant_id,
                (func.lower(Assignment.name).like(search_term) |
                 func.lower(Assignment.assignment_type).like(search_term))
            ).limit(5)

            student_result = await session.execute(student_query)
            assignment_result = await session.execute(assignment_query)

            students = student_result.scalars().all()
            assignments = assignment_result.scalars().all()

            results = [
                {'id': s.id, 'name': s.full_name, 'email': s.email, 'type': 'student'}
                for s in students
            ] + [
                {
                    'id': a.id,
                    'name': a.name,
                    'type': a.assignment_type,
                    'assignment_type': 'assignment'
                }
                for a in assignments
            ]

            return {'results': results}


@router.get("/student/{student_id}/grades")
async def get_student_grades(
    student_id: int, tenant_id: str = Depends(get_current_tenant_id)
):
    async with get_tenant_db_session(tenant_id) as session:
        student = await ensure_tenant_resource_access(session, Student, student_id, tenant_id)

        grades_query = select(
            Grade.id,
            Grade.points_earned,
            Grade.points_possible,
            Grade.created_at,
            Assignment.name,
            Assignment.assignment_type,
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

        grade_list = []
        for g in grades:
            percentage = (g.points_earned / g.points_possible) * 100 if g.points_possible > 0 else 0
            if percentage >= 90: letter_grade = "A"
            elif percentage >= 80: letter_grade = "B"
            elif percentage >= 70: letter_grade = "C"
            elif percentage >= 60: letter_grade = "D"
            else: letter_grade = "F"
            
            grade_list.append({
                'id': g.id,
                'points_earned': g.points_earned,
                'points_possible': g.points_possible,
                'percentage': round(percentage, 2),
                'letter_grade': letter_grade,
                'created_at': g.created_at.isoformat() if g.created_at else None,
                'assignment': {
                    'name': g.name,
                    'type': g.assignment_type,
                    'max_points': g.max_points,
                    'due_date': g.due_date.isoformat() if g.due_date else None
                }
            })

        return {
            'student': {
                'id': student.id,
                'name': student.full_name,
                'email': student.email,
                'grade_level': student.grade_level
            },
            'grades': grade_list
        }


@router.get("/assignment/{assignment_id}/grades")
async def get_assignment_grades(
    assignment_id: int, tenant_id: str = Depends(get_current_tenant_id)
):
    async with get_tenant_db_session(tenant_id) as session:
        assignment = await ensure_tenant_resource_access(session, Assignment, assignment_id, tenant_id)

        grades_query = select(
            Grade.id,
            Grade.points_earned,
            Grade.points_possible,
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

        total_grades = len(grades)
        percentages = []
        grade_list = []
        
        for g in grades:
            percentage = (g.points_earned / g.points_possible) * 100 if g.points_possible > 0 else 0
            percentages.append(percentage)
            
            if percentage >= 90: letter_grade = "A"
            elif percentage >= 80: letter_grade = "B"
            elif percentage >= 70: letter_grade = "C"
            elif percentage >= 60: letter_grade = "D"
            else: letter_grade = "F"
            
            grade_list.append({
                'id': g.id,
                'points_earned': g.points_earned,
                'points_possible': g.points_possible,
                'percentage': round(percentage, 2),
                'letter_grade': letter_grade,
                'created_at': g.created_at.isoformat() if g.created_at else None,
                'student': {
                    'name': f"{g.first_name} {g.last_name}",
                    'email': g.email,
                    'grade_level': g.grade_level
                }
            })

        avg_percentage = sum(percentages) / len(percentages) if percentages else None
        highest_percentage = max(percentages) if percentages else None
        lowest_percentage = min(percentages) if percentages else None

        return {
            'assignment': {
                'id': assignment.id,
                'name': assignment.name,
                'type': assignment.assignment_type,
                'max_points': assignment.max_points,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None
            },
            'statistics': {
                'total_submissions': total_grades,
                'average_percentage': round(avg_percentage, 2) if avg_percentage else None,
                'highest_percentage': highest_percentage,
                'lowest_percentage': lowest_percentage
            },
            'grades': grade_list
        }
