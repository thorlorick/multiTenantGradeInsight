from fastapi import APIRouter, Depends, Request, HTTPException
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/students", tags=["students"])

# Simplified Pydantic models
class StudentBase(BaseModel):
    student_number: str
    first_name: str
    last_name: str

class StudentCreate(StudentBase):
    pass

class StudentResponse(StudentBase):
    id: int

    class Config:
        orm_mode = True

# Dependency to get tenant_id from request.state
def get_tenant_id(request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(400, "Tenant context missing")
    return tenant_id

# Simulate DB with in-memory list (replace with your ORM)
STUDENTS = []

@router.post("/", response_model=StudentResponse)
async def create_student(student: StudentCreate, tenant_id: str = Depends(get_tenant_id)):
    new_id = len(STUDENTS) + 1
    student_dict = student.dict()
    student_dict.update({"id": new_id, "tenant_id": tenant_id})
    STUDENTS.append(student_dict)
    return student_dict

@router.get("/", response_model=List[StudentResponse])
async def list_students(tenant_id: str = Depends(get_tenant_id)):
    return [s for s in STUDENTS if s["tenant_id"] == tenant_id]

@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: int, tenant_id: str = Depends(get_tenant_id)):
    for s in STUDENTS:
        if s["id"] == student_id and s["tenant_id"] == tenant_id:
            return s
    raise HTTPException(404, "Student not found")
#empty
