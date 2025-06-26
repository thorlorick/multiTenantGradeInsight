"""
Simplified Dashboard API
Matches your CSV-based gradebook system

Endpoints:
- Upload CSV and load grades
- View gradebook data
- Basic stats for parents
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import io

from app.database.connection import get_tenant_db_session
from app.database.models import Student, Assignment, Grade, Tenant, create_tenant_session, parse_csv_and_load_grades
from app.middleware.tenant import get_current_tenant_id

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.post("/upload-csv")
async def upload_csv_grades(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Upload CSV file and load grades into database"""
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "File must be a CSV")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        async with get_tenant_db_session(tenant_id) as session:
            # Parse and load grades
            result = parse_csv_and_load_grades(session, uuid.UUID(tenant_id), csv_content)
            
            return {
                'success': True,
                'message': f"Loaded {result['grades_processed']} grades for {result['students_processed']} students across {result['assignments_created']} assignments",
                'details': result
            }
            
    except Exception as e:
        raise HTTPException(400, f"Error processing CSV: {str(e)}")


@router.get("/gradebook")
async def get_gradebook_data(tenant_id: str = Depends(get_current_tenant_id)):
    """Get complete gradebook data for display"""
    
    async with get_tenant_db_session(tenant_id) as session:
        tenant_query = create_tenant_session(session, uuid.UUID(tenant_id))
        data = tenant_query.get_grades_for_display()
        
        return {
            'success': True,
            'data': data,
            'summary': {
                'total_students': len(data['students']),
                'total_assignments': len(data['assignments'])
            }
        }


@router.get("/student/{email}/grades")
async def get_student_grades_by_email(
    email: str, 
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Get grades for a specific student (for parents)"""
    
    async with get_tenant_db_session(tenant_id) as session:
        tenant_query = create_tenant_session(session, uuid.UUID(tenant_id))
        
        # Find student by email
        student = tenant_query.query(Student).filter(Student.email == email).first()
        if not student:
            raise HTTPException(404, "Student not found")
        
        # Get student's grades
        grades = tenant_query.query(Grade).filter(Grade.student_id == student.id).all()
        assignments = tenant_query.get_all_assignments()
        assignment_lookup = {a.id: a for a in assignments}
        
        student_grades = []
        for grade in grades:
            assignment = assignment_lookup.get(grade.assignment_id)
            if assignment:
                student_grades.append({
                    'assignment_name': assignment.name,
                    'assignment_date': assignment.assignment_date.strftime('%Y-%m-%d') if assignment.assignment_date else None,
                    'points_earned': grade.points_earned,
                    'total_points': assignment.total_points,
                    'percentage': grade.percentage
                })
        
        # Calculate overall average
        percentages = [g['percentage'] for g in student_grades if g['percentage'] is not None]
        overall_average = round(sum(percentages) / len(percentages), 1) if percentages else None
        
        return {
            'student': {
                'name': student.full_name,
                'email': student.email
            },
            'grades': student_grades,
            'overall_average': overall_average,
            'total_assignments': len(student_grades)
        }


@router.get("/stats")
async def get_basic_stats(tenant_id: str = Depends(get_current_tenant_id)):
    """Get basic statistics for the gradebook"""
    
    async with get_tenant_db_session(tenant_id) as session:
        # Count totals
        total_students = session.query(Student).filter(
            Student.tenant_id == uuid.UUID(tenant_id),
            Student.is_active == True
        ).count()
        
        total_assignments = session.query(Assignment).filter(
            Assignment.tenant_id == uuid.UUID(tenant_id),
            Assignment.is_active == True
        ).count()
        
        total_grades = session.query(Grade).filter(
            Grade.tenant_id == uuid.UUID(tenant_id)
        ).count()
        
        # Calculate average grade
        avg_result = session.query(func.avg(Grade.points_earned / Assignment.total_points * 100)).join(
            Assignment, Grade.assignment_id == Assignment.id
        ).filter(
            Grade.tenant_id == uuid.UUID(tenant_id),
            Grade.points_earned.isnot(None)
        ).scalar()
        
        average_percentage = round(avg_result, 1) if avg_result else None
        
        return {
            'total_students': total_students,
            'total_assignments': total_assignments,
            'total_grades': total_grades,
            'average_percentage': average_percentage,
            'completion_rate': round((total_grades / (total_students * total_assignments) * 100), 1) if total_students and total_assignments else 0
        }


@router.get("/assignment/{assignment_name}/stats")
async def get_assignment_stats(
    assignment_name: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Get statistics for a specific assignment"""
    
    async with get_tenant_db_session(tenant_id) as session:
        tenant_query = create_tenant_session(session, uuid.UUID(tenant_id))
        
        # Find assignment
        assignment = tenant_query.query(Assignment).filter(Assignment.name == assignment_name).first()
        if not assignment:
            raise HTTPException(404, "Assignment not found")
        
        # Get all grades for this assignment
        grades = tenant_query.query(Grade).filter(Grade.assignment_id == assignment.id).all()
        
        if not grades:
            return {
                'assignment': {
                    'name': assignment.name,
                    'total_points': assignment.total_points,
                    'date': assignment.assignment_date.strftime('%Y-%m-%d') if assignment.assignment_date else None
                },
                'stats': {
                    'total_submissions': 0,
                    'average_percentage': None,
                    'highest_score': None,
                    'lowest_score': None
                }
            }
        
        # Calculate statistics
        percentages = [g.percentage for g in grades if g.percentage is not None]
        scores = [g.points_earned for g in grades if g.points_earned is not None]
        
        return {
            'assignment': {
                'name': assignment.name,
                'total_points': assignment.total_points,
                'date': assignment.assignment_date.strftime('%Y-%m-%d') if assignment.assignment_date else None
            },
            'stats': {
                'total_submissions': len(grades),
                'average_percentage': round(sum(percentages) / len(percentages), 1) if percentages else None,
                'highest_score': max(scores) if scores else None,
                'lowest_score': min(scores) if scores else None,
                'highest_percentage': max(percentages) if percentages else None,
                'lowest_percentage': min(percentages) if percentages else None
            }
        }


@router.get("/download-template")
async def download_csv_template():
    """Download CSV template matching your format"""
    
    csv_content = """last_name,first_name,email,Math Test,Essay 1,Science Lab
DATE,-,-,2025-06-01,2025-06-03,2025-06-05
POINTS,-,-,100,100,100
Smith,Alice,alice.smith@example.com,85,90,78
Johnson,Bob,bob.johnson@example.com,88,92,81
Brown,Charlie,charlie.brown@example.com,92,85,89"""
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gradebook_template.csv"}
    )


@router.get("/export-grades")
async def export_grades_csv(tenant_id: str = Depends(get_current_tenant_id)):
    """Export current grades in the same CSV format"""
    
    async with get_tenant_db_session(tenant_id) as session:
        tenant_query = create_tenant_session(session, uuid.UUID(tenant_id))
        data = tenant_query.get_grades_for_display()
        
        if not data['students'] or not data['assignments']:
            raise HTTPException(404, "No data to export")
        
        # Build CSV content
        csv_lines = []
        
        # Header row
        headers = ['last_name', 'first_name', 'email'] + [a['name'] for a in data['assignments']]
        csv_lines.append(','.join(headers))
        
        # Date row
        dates = ['DATE', '-', '-'] + [a['date'] or '-' for a in data['assignments']]
        csv_lines.append(','.join(dates))
        
        # Points row
        points = ['POINTS', '-', '-'] + [str(int(a['total_points'])) for a in data['assignments']]
        csv_lines.append(','.join(points))
        
        # Student data rows
        for student in data['students']:
            row = [
                student['last_name'],
                student['first_name'],
                student['email']
            ]
            
            for assignment in data['assignments']:
                grade = student['grades'].get(assignment['id'])
                if grade and grade['points_earned'] is not None:
                    row.append(str(grade['points_earned']))
                else:
                    row.append('-')
            
            csv_lines.append(','.join(row))
        
        csv_content = '\n'.join(csv_lines)
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=exported_grades.csv"}
        )


@router.delete("/clear-data")
async def clear_all_data(tenant_id: str = Depends(get_current_tenant_id)):
    """Clear all grades, assignments, and students for this tenant"""
    
    async with get_tenant_db_session(tenant_id) as session:
        # Delete in correct order (foreign key constraints)
        session.query(Grade).filter(Grade.tenant_id == uuid.UUID(tenant_id)).delete()
        session.query(Assignment).filter(Assignment.tenant_id == uuid.UUID(tenant_id)).delete()
        session.query(Student).filter(Student.tenant_id == uuid.UUID(tenant_id)).delete()
        
        session.commit()
        
        return {
            'success': True,
            'message': 'All data cleared for this tenant'
        }


@router.get("/search")
async def search_students(
    q: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Simple search for students by name or email"""
    
    if not q or len(q) < 2:
        return {'results': []}
    
    async with get_tenant_db_session(tenant_id) as session:
        tenant_query = create_tenant_session(session, uuid.UUID(tenant_id))
        
        search_term = f"%{q.lower()}%"
        students = tenant_query.query(Student).filter(
            (func.lower(Student.first_name).like(search_term)) |
            (func.lower(Student.last_name).like(search_term)) |
            (func.lower(Student.email).like(search_term))
        ).limit(10).all()
        
        return {
            'results': [
                {
                    'name': student.full_name,
                    'email': student.email,
                    'id': student.id
                }
                for student in students
            ]
        }


# Simple health check
@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        'status': 'healthy',
        'service': 'Simple Multi-Tenant Gradebook API'
    }
