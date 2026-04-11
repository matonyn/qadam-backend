from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user

router = APIRouter(prefix="/discounts", tags=["discounts"])


def _discount_out(d: models.Discount) -> schemas.DiscountOut:
    return schemas.DiscountOut(
        id=d.id,
        vendorName=d.vendor_name,
        vendorLogo=d.vendor_logo,
        title=d.title,
        description=d.description,
        discountPercentage=d.discount_percentage,
        category=d.category,
        validUntil=d.valid_until,
        code=d.code,
        terms=d.terms,
        isVerified=d.is_verified,
    )


@router.get("", response_model=schemas.ApiResponse[list[schemas.DiscountOut]])
def get_discounts(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.Discount)
    if category:
        q = q.filter(models.Discount.category == category)
    discounts = q.all()
    return schemas.ApiResponse(success=True, data=[_discount_out(d) for d in discounts])


@router.get("/{discount_id}", response_model=schemas.ApiResponse[schemas.DiscountOut])
def get_discount(
    discount_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    d = db.query(models.Discount).filter(models.Discount.id == discount_id).first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return schemas.ApiResponse(success=True, data=_discount_out(d))


@router.post("/{discount_id}/verify", response_model=schemas.ApiResponse[schemas.EligibilityResult])
def verify_eligibility(
    discount_id: str,
    body: schemas.VerifyEligibilityRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    d = db.query(models.Discount).filter(models.Discount.id == discount_id).first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Verify that the student ID matches the authenticated user
    eligible = current_user.student_id == body.studentId
    reason = None if eligible else "Student ID does not match your account"
    return schemas.ApiResponse(success=True, data=schemas.EligibilityResult(eligible=eligible, reason=reason))
