from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.project_service import ProjectService
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project for the authenticated user.
    """
    return ProjectService.create_project(db=db, project_in=project_in, user_id=current_user.id)

@router.get("", response_model=List[ProjectResponse])
def get_user_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all projects belonging to the authenticated user.
    """
    return ProjectService.get_user_projects(db=db, user_id=current_user.id)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific project by ID (must be owned by the user).
    """
    return ProjectService.get_project_by_id(db=db, project_id=project_id, user_id=current_user.id)

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update project details (must be owned by the user).
    """
    return ProjectService.update_project(
        db=db, project_id=project_id, project_in=project_in, user_id=current_user.id
    )

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a project (must be owned by the user).
    """
    return ProjectService.delete_project(db=db, project_id=project_id, user_id=current_user.id)
