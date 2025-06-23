from fastapi import APIRouter, Depends, Request, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/grades", tags=["grades"])

# Simple Pydantic models for Grade
class GradeBase(BaseModel):
    student_id: int
    assignment_id: int
    points_earned: Optional[float] = None
    points_possible: float

class GradeCreate(GradeBase):
    pass

class GradeResponse(GradeBase):
    id: int
    graded_at: Optional[datetime]

    class Config:
        orm_mode = True

# Dependency to get tenant_id from request.state
def get_tenant_id(request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(400, "Tenant context missing")
    return tenant_id

# Fake DB list (replace with your ORM session queries)
GRADES = []

@router.post("/", response_model=GradeResponse)
async def create_grade(grade: GradeCreate, tenant_id: str = Depends(get_tenant_id)):
    new_id = len(GRADES) + 1
    grade_dict = grade.dict()
    grade_dict.update({"id": new_id, "tenant_id": tenant_id, "graded_at": datetime.utcnow() if grade.points_earned is not None else None})
    GRADES.append(grade_dict)
    return grade_dict

@router.get("/", response_model=List[GradeResponse])
async def list_grades(tenant_id: str = Depends(get_tenant_id)):
    return [g for g in GRADES if g["tenant_id"] == tenant_id]

@router.get("/{grade_id}", response_model=GradeResponse)
async def get_grade(grade_id: int, tenant_id: str = Depends(get_tenant_id)):
    for g in GRADES:
        if g["id"] == grade_id and g["tenant_id"] == tenant_id:
            return g
    raise HTTPException(404, "Grade not found")

