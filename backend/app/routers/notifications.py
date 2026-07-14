from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.notification import TimeoutRule, EscalationRule, Notification
from app.models.order import Order, OrderProgressStep
from app.models.system import StepOwner, User

router = APIRouter(prefix="/api/notification-rules", tags=["notifications"])


class TimeoutRuleIn(BaseModel):
    step_name: str
    days_allowed: int = Field(ge=1)
    warning_threshold_days: int = Field(1, ge=0)


class TimeoutRuleOut(TimeoutRuleIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/timeout", response_model=list[TimeoutRuleOut])
def list_timeout_rules(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(TimeoutRule).order_by(TimeoutRule.id).all()


@router.post("/timeout", response_model=TimeoutRuleOut)
def create_timeout_rule(
    payload: TimeoutRuleIn, db: Session = Depends(get_db), _=Depends(require_role("admin", "supervisor"))
):
    rule = TimeoutRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/timeout/{rule_id}", response_model=TimeoutRuleOut)
def update_timeout_rule(
    rule_id: int,
    payload: TimeoutRuleIn,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "supervisor")),
):
    rule = db.get(TimeoutRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


class EscalationRuleIn(BaseModel):
    step_name: str
    overdue_days: int = Field(ge=0)
    notify_role: str


class EscalationRuleOut(EscalationRuleIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/escalation", response_model=list[EscalationRuleOut])
def list_escalation_rules(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(EscalationRule).order_by(EscalationRule.overdue_days).all()


@router.post("/escalation", response_model=EscalationRuleOut)
def create_escalation_rule(
    payload: EscalationRuleIn, db: Session = Depends(get_db), _=Depends(require_role("admin", "supervisor"))
):
    rule = EscalationRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def _notify(db: Session, user_id: int | None, message: str, level: str) -> int:
    """Creates a notification unless an identical unread one already exists (user_id
    None means broadcast). Returns 1 if created, 0 if deduplicated."""
    q = db.query(Notification).filter(Notification.message == message, Notification.is_read.is_(False))
    q = q.filter(Notification.user_id == user_id) if user_id is not None else q.filter(Notification.user_id.is_(None))
    if q.first():
        return 0
    db.add(Notification(user_id=user_id, message=message, level=level))
    return 1


@router.post("/scan")
def scan_and_notify(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Evaluates timeout/escalation rules against in-progress order steps and creates
    notifications. Meant to be called periodically (dashboard load or a cron job)."""
    now = datetime.utcnow()
    timeout_rules = {r.step_name: r for r in db.query(TimeoutRule).all()}
    created = 0

    steps = (
        db.query(OrderProgressStep)
        .join(Order, Order.id == OrderProgressStep.order_id)
        .filter(OrderProgressStep.status == "in_progress", Order.status == "in_progress")
        .all()
    )
    for step in steps:
        rule = timeout_rules.get(step.step_name)
        if step.due_at is None and rule and step.started_at:
            # backfill deadlines for steps that started before the rule existed
            step.due_at = step.started_at + timedelta(days=rule.days_allowed)
        if step.due_at is None:
            continue

        order_no = step.order.order_no
        owners = db.query(StepOwner).filter(StepOwner.step_name == step.step_name).all()
        owner_ids = [o.user_id for o in owners] or [None]  # no owner configured -> broadcast

        if now > step.due_at:
            days_overdue = (now - step.due_at).days
            message = f"Order {order_no}: step '{step.step_name}' is overdue"
            for user_id in owner_ids:
                created += _notify(db, user_id, message, "warning")
            escalations = (
                db.query(EscalationRule)
                .filter(EscalationRule.step_name == step.step_name, EscalationRule.overdue_days <= days_overdue)
                .all()
            )
            for esc in escalations:
                esc_message = (
                    f"Order {order_no}: step '{step.step_name}' overdue by {days_overdue} day(s) — escalated"
                )
                recipients = db.query(User).filter(User.role == esc.notify_role, User.is_active.is_(True)).all()
                for user in recipients:
                    created += _notify(db, user.id, esc_message, "critical")
        elif rule and now >= step.due_at - timedelta(days=rule.warning_threshold_days):
            message = f"Order {order_no}: step '{step.step_name}' is due by {step.due_at:%Y-%m-%d}"
            for user_id in owner_ids:
                created += _notify(db, user_id, message, "info")

    db.commit()
    return {"notifications_created": created, "steps_checked": len(steps)}
