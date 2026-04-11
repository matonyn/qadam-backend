from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Course).filter(models.Course.user_id == current_user.id)
    if semester:
        q = q.filter(models.Course.semester == semester)
    courses = q.all()
    return schemas.ApiResponse(success=True, data=[_course_out(c) for c in courses])


@router.get("/plan", response_model=schemas.ApiResponse[schemas.AcademicPlanOut])
def get_academic_plan(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    plan = db.query(models.AcademicPlan).filter(models.AcademicPlan.user_id == current_user.id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic plan not found")

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    courses = db.query(models.Course).filter(models.Course.user_id == current_user.id).all()

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
