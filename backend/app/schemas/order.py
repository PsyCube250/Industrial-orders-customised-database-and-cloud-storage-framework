from datetime import datetime, date

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    customer_name: str
    product_name: str = ""
    quantity: int = Field(0, ge=0)
    delivery_date: date | None = None
    notes: str = ""


class OrderUpdate(BaseModel):
    customer_name: str | None = None
    product_name: str | None = None
    quantity: int | None = Field(None, ge=0)
    notes: str | None = None


class OrderChangeAction(BaseModel):
    change_type: str  # delivery_date | cancel | pause | resume
    new_delivery_date: date | None = None  # required when change_type == delivery_date


class OrderAttachmentOut(BaseModel):
    id: int
    file_name: str
    file_path: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class OrderProgressStepOut(BaseModel):
    id: int
    step_name: str
    sequence: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    due_at: datetime | None
    is_overdue: bool

    class Config:
        from_attributes = True


class OrderChangeLogOut(BaseModel):
    id: int
    change_type: str
    old_value: str
    new_value: str
    changed_at: datetime

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    order_no: str
    customer_name: str
    product_name: str
    quantity: int
    delivery_date: date | None
    status: str
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderDetailOut(OrderOut):
    attachments: list[OrderAttachmentOut] = []
    progress_steps: list[OrderProgressStepOut] = []
    change_logs: list[OrderChangeLogOut] = []


class OrderStatsOut(BaseModel):
    total_orders: int
    on_time_rate: float
    delay_ranking: list[dict]
    step_duration_avg_hours: list[dict]
    product_quantity_totals: list[dict]
