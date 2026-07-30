import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    BankQuestionCreate,
    BankQuestionDetail,
    BankQuestionLineageOut,
    BankQuestionList,
    BankQuestionOut,
    BankQuestionSolutionCreate,
    BankQuestionSolutionOut,
    BankQuestionStats,
    BankQuestionUpdate,
    BankSourceOut,
)
from app.models.rbac import User
from app.repositories.question_bank_repository import QuestionBankRepository
from app.services.question_bank_service import QuestionBankService

router = APIRouter(prefix="/api/question-bank", tags=["question_bank"])

MODULE = "question_bank"


@router.get("/stats", response_model=BankQuestionStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return BankQuestionStats(**QuestionBankRepository(db).stats())


@router.get("/sources", response_model=list[BankSourceOut])
def list_sources(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, _total = QuestionBankRepository(db).list_sources(limit=limit, offset=offset)
    return items


@router.get("", response_model=BankQuestionList)
def list_questions(
    search: str | None = None,
    exam: str | None = None,
    year: int | None = None,
    subject_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    question_type: str | None = None,
    difficulty: str | None = None,
    status: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = QuestionBankRepository(db).query(
        search=search,
        exam=exam,
        year=year,
        subject_id=subject_id,
        unit_id=unit_id,
        chapter_id=chapter_id,
        topic_id=topic_id,
        question_type=question_type,
        difficulty=difficulty,
        status=status,
        limit=limit,
        offset=offset,
    )
    return BankQuestionList(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=BankQuestionDetail)
def create_question(
    payload: BankQuestionCreate,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:create")),
):
    return QuestionBankService(db).create(
        **payload.model_dump(exclude={"topics", "options", "source"}),
        topics=[t.model_dump() for t in payload.topics],
        options=[o.model_dump() for o in payload.options],
        source=payload.source.model_dump() if payload.source else None,
        created_by=user.id,
    )


@router.get("/{question_id}", response_model=BankQuestionDetail)
def get_question(
    question_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    question = QuestionBankRepository(db).get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.put("/{question_id}", response_model=BankQuestionDetail)
def update_question(
    question_id: uuid.UUID,
    payload: BankQuestionUpdate,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:update")),
):
    repo = QuestionBankRepository(db)
    question = repo.get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    updates = payload.model_dump(exclude={"topics", "options"}, exclude_unset=True)
    topics = [t.model_dump() for t in payload.topics] if payload.topics is not None else None
    options = [o.model_dump() for o in payload.options] if payload.options is not None else None
    return QuestionBankService(db).update(question, updates, topics=topics, options=options, user_id=user.id)


@router.post("/{question_id}/approve", response_model=BankQuestionOut)
def approve_question(
    question_id: uuid.UUID,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:update")),
):
    repo = QuestionBankRepository(db)
    question = repo.get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionBankService(db).set_status(question, "approved", user_id=user.id)


@router.post("/{question_id}/reject", response_model=BankQuestionOut)
def reject_question(
    question_id: uuid.UUID,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:update")),
):
    repo = QuestionBankRepository(db)
    question = repo.get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionBankService(db).set_status(question, "rejected", user_id=user.id)


@router.delete("/{question_id}")
def delete_question(
    question_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:delete")),
):
    repo = QuestionBankRepository(db)
    question = repo.get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    QuestionBankService(db).delete(question)
    return {"status": "deleted"}


@router.get("/{question_id}/lineage", response_model=list[BankQuestionLineageOut])
def get_lineage(
    question_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = QuestionBankRepository(db)
    if not repo.get(question_id):
        raise HTTPException(status_code=404, detail="Question not found")
    return repo.lineage(question_id)


@router.post("/{question_id}/solutions", response_model=BankQuestionSolutionOut)
def add_solution(
    question_id: uuid.UUID,
    payload: BankQuestionSolutionCreate,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:update")),
):
    repo = QuestionBankRepository(db)
    if not repo.get(question_id):
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionBankService(db).add_solution(
        question_id, payload.solution_text, payload.explanation, payload.source_type, payload.source_url
    )


@router.delete("/solutions/{solution_id}")
def delete_solution(
    solution_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:update")),
):
    if not QuestionBankRepository(db).delete_solution(solution_id):
        raise HTTPException(status_code=404, detail="Solution not found")
    return {"status": "deleted"}
