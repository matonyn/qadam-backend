from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase
from app.seed import ensure_academic_plan

router = APIRouter(prefix="/academic", tags=["academic"])

DAY_MAP = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}


def _course_out(c: models.Course) -> schemas.CourseOut:
    schedule = [schemas.CourseScheduleItem(**item) for item in (c.schedule or [])]
    return schemas.CourseOut(
        id=c.id,
        code=c.code,
        name=c.name,
        credits=c.credits,
        grade=c.grade,
        gradePoints=c.grade_points,
        semester=c.semester,
        instructor=c.instructor,
        schedule=schedule,
    )


@router.get("/courses", response_model=schemas.ApiResponse[list[schemas.CourseOut]])
def get_courses(
    semester: str | None = Query(None),
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    q = sb.table("courses").select("*").eq("user_id", current_user.id)
    if semester:
        q = q.eq("semester", semester)
    res = q.execute()
    courses = [models.Course.from_row(r) for r in (res.data or [])]
    return schemas.ApiResponse(success=True, data=[_course_out(c) for c in courses])


@router.get("/plan", response_model=schemas.ApiResponse[schemas.AcademicPlanOut])
def get_academic_plan(
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    plan = ensure_academic_plan(sb, current_user.id)

    return schemas.ApiResponse(
        success=True,
        data=schemas.AcademicPlanOut(
            totalCreditsRequired=plan.total_credits_required,
            creditsCompleted=plan.credits_completed,
            creditsInProgress=plan.credits_in_progress,
            gpa=plan.gpa,
            standing=plan.standing,
            expectedGraduation=plan.expected_graduation,
            major=plan.major,
            minor=plan.minor,
        ),
    )


@router.get("/schedule", response_model=schemas.ApiResponse[list[schemas.CourseOut]])
def get_schedule(
    date_param: str | None = Query(None, alias="date"),
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    res = sb.table("courses").select("*").eq("user_id", current_user.id).execute()
    courses = [models.Course.from_row(r) for r in (res.data or [])]

    if date_param:
        try:
            d = date.fromisoformat(date_param)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format, use YYYY-MM-DD")

        target_day = DAY_MAP[d.weekday()]
        result = []
        for c in courses:
            matching = [s for s in (c.schedule or []) if s.get("day") == target_day]
            if matching:
                filtered = schemas.CourseOut(
                    id=c.id,
                    code=c.code,
                    name=c.name,
                    credits=c.credits,
                    grade=c.grade,
                    gradePoints=c.grade_points,
                    semester=c.semester,
                    instructor=c.instructor,
                    schedule=[schemas.CourseScheduleItem(**s) for s in matching],
                )
                result.append(filtered)
        return schemas.ApiResponse(success=True, data=result)

    return schemas.ApiResponse(success=True, data=[_course_out(c) for c in courses])
