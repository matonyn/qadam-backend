from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user
import uuid

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _review_out(r: models.Review) -> schemas.ReviewOut:
    created = r.created_at.isoformat() + "Z" if r.created_at else ""
    # Build display name from user
    user_name = f"{r.user.first_name} {r.user.last_name[0]}." if r.user else "Unknown"
    return schemas.ReviewOut(
        id=r.id,
        userId=r.user_id,
        userName=user_name,
        userAvatar=r.user.avatar if r.user else None,
        targetId=r.target_id,
        targetType=r.target_type,
        targetName=r.target_name,
        rating=r.rating,
        comment=r.comment,
        sentiment=r.sentiment,
        helpful=r.helpful,
        createdAt=created,
    )


def _calc_sentiment(rating: int) -> str:
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"


@router.get("", response_model=schemas.ApiResponse[list[schemas.ReviewOut]])
def get_reviews(
    targetId: str | None = Query(None),
    targetType: str | None = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.Review)
    if targetId:
        q = q.filter(models.Review.target_id == targetId)
    if targetType:
        q = q.filter(models.Review.target_type == targetType)
    reviews = q.order_by(models.Review.created_at.desc()).all()
    return schemas.ApiResponse(success=True, data=[_review_out(r) for r in reviews])


@router.post("", response_model=schemas.ApiResponse[schemas.ReviewOut])
def create_review(
    body: schemas.CreateReviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5")

    review = models.Review(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        target_id=body.targetId,
        target_type=body.targetType,
        target_name=body.targetName,
        rating=body.rating,
        comment=body.comment,
        sentiment=_calc_sentiment(body.rating),
        helpful=0,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return schemas.ApiResponse(success=True, data=_review_out(review))


@router.post("/{review_id}/helpful", response_model=schemas.ApiResponse[schemas.HelpfulResult])
def mark_helpful(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    already = db.query(models.ReviewHelpful).filter(
        models.ReviewHelpful.review_id == review_id,
        models.ReviewHelpful.user_id == current_user.id,
    ).first()
    if already:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already marked helpful")

    db.add(models.ReviewHelpful(review_id=review_id, user_id=current_user.id))
    review.helpful += 1
    db.commit()
    return schemas.ApiResponse(success=True, data=schemas.HelpfulResult(helpful=review.helpful))


@router.post("/{review_id}/report", response_model=schemas.ApiResponse[None])
def report_review(
    review_id: str,
    body: schemas.ReportReviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    db.add(models.ReviewReport(review_id=review_id, user_id=current_user.id, reason=body.reason))
    db.commit()
    return schemas.ApiResponse(success=True, data=None)
