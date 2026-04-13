import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _review_out(r: models.Review) -> schemas.ReviewOut:
    created = r.created_at.isoformat() + "Z" if r.created_at else ""
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
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    q = sb.table("reviews").select("*")
    if targetId:
        q = q.eq("target_id", targetId)
    if targetType:
        q = q.eq("target_type", targetType)
    res = q.order("created_at", desc=True).execute()
    revs = [models.Review.from_row(r) for r in (res.data or [])]
    uids = list({r.user_id for r in revs})
    users: dict[str, models.User] = {}
    if uids:
        ures = sb.table("users").select("*").in_("id", uids).execute()
        for row in ures.data or []:
            users[row["id"]] = models.User.from_row(row)
    for r in revs:
        r.user = users.get(r.user_id)
    return schemas.ApiResponse(success=True, data=[_review_out(r) for r in revs])


@router.post("", response_model=schemas.ApiResponse[schemas.ReviewOut])
def create_review(
    body: schemas.CreateReviewRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5")

    row = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "target_id": body.targetId,
        "target_type": body.targetType,
        "target_name": body.targetName,
        "rating": body.rating,
        "comment": body.comment,
        "sentiment": _calc_sentiment(body.rating),
        "helpful": 0,
    }
    ins = sb.table("reviews").insert(row).execute()
    rev = models.Review.from_row((ins.data or [row])[0])
    rev.user = current_user
    return schemas.ApiResponse(success=True, data=_review_out(rev))


@router.post("/{review_id}/helpful", response_model=schemas.ApiResponse[schemas.HelpfulResult])
def mark_helpful(
    review_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    rres = sb.table("reviews").select("*").eq("id", review_id).limit(1).execute()
    rows = rres.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    review = models.Review.from_row(rows[0])

    ex = (
        sb.table("review_helpful")
        .select("id")
        .eq("review_id", review_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    if ex.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already marked helpful")

    sb.table("review_helpful").insert(
        {"id": str(uuid.uuid4()), "review_id": review_id, "user_id": current_user.id}
    ).execute()
    new_helpful = review.helpful + 1
    sb.table("reviews").update({"helpful": new_helpful}).eq("id", review_id).execute()
    return schemas.ApiResponse(success=True, data=schemas.HelpfulResult(helpful=new_helpful))


@router.post("/{review_id}/report", response_model=schemas.ApiResponse[None])
def report_review(
    review_id: str,
    body: schemas.ReportReviewRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    rres = sb.table("reviews").select("id").eq("id", review_id).limit(1).execute()
    if not rres.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    sb.table("review_reports").insert(
        {
            "id": str(uuid.uuid4()),
            "review_id": review_id,
            "user_id": current_user.id,
            "reason": body.reason,
        }
    ).execute()
    return schemas.ApiResponse(success=True, data=None)
