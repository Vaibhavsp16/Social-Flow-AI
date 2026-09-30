from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectService:
    @staticmethod
    def get_user_projects(db: Session, user_id: int) -> list[Project]:
        return db.query(Project).filter(Project.user_id == user_id).order_by(Project.created_at.desc()).all()

    @staticmethod
    def get_project_by_id(db: Session, project_id: int, user_id: int) -> Project:
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you do not have permission to access it."
            )
        return project

    @staticmethod
    def create_project(db: Session, project_in: ProjectCreate, user_id: int) -> Project:
        db_project = Project(
            user_id=user_id,
            name=project_in.name.strip(),
            industry=project_in.industry,
            description=project_in.description.strip() if project_in.description else None
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    @staticmethod
    def update_project(db: Session, project_id: int, project_in: ProjectUpdate, user_id: int) -> Project:
        project = ProjectService.get_project_by_id(db, project_id, user_id)
        if project_in.name is not None:
            project.name = project_in.name.strip()
        if project_in.industry is not None:
            project.industry = project_in.industry
        if project_in.description is not None:
            project.description = project_in.description.strip()
        
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def delete_project(db: Session, project_id: int, user_id: int) -> dict:
        project = ProjectService.get_project_by_id(db, project_id, user_id)
        db.delete(project)
        db.commit()
        return {"message": "Project deleted successfully", "id": project_id}
