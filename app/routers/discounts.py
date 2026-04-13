from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase

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
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    q = sb.table("discounts").select("*")
    if category:
        q = q.eq("category", category)
    res = q.execute()
    discounts = [models.Discount.from_row(r) for r in (res.data or [])]
    return schemas.ApiResponse(success=True, data=[_discount_out(d) for d in discounts])


@router.get("/{discount_id}", response_model=schemas.ApiResponse[schemas.DiscountOut])
def get_discount(
    discount_id: str,
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    res = sb.table("discounts").select("*").eq("id", discount_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return schemas.ApiResponse(success=True, data=_discount_out(models.Discount.from_row(rows[0])))


@router.post("/{discount_id}/verify", response_model=schemas.ApiResponse[schemas.EligibilityResult])
def verify_eligibility(
    discount_id: str,
    body: schemas.VerifyEligibilityRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    res = sb.table("discounts").select("*").eq("id", discount_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    d = models.Discount.from_row(rows[0])

    try:
        valid_until = date.fromisoformat(d.valid_until) if d.valid_until else date.min
    except (TypeError, ValueError):
        valid_until = date.min

    if valid_until < date.today():
        return schemas.ApiResponse(
            success=True,
            data=schemas.EligibilityResult(eligible=False, reason="Discount is no longer valid"),
        )

    if current_user.student_id != body.studentId:
        return schemas.ApiResponse(
            success=True,
            data=schemas.EligibilityResult(eligible=False, reason="Student ID does not match your account"),
        )

    return schemas.ApiResponse(success=True, data=schemas.EligibilityResult(eligible=True, reason=None))
