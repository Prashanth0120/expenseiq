import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, Base, get_db
import models
import schemas

from security import hash_password, verify_password
from auth import create_access_token, get_current_user


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("ExpenseIQ logging started")


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="ExpenseIQ API",
    description="Personal Expense Management API",
    version="1.0.0"
)
@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):
    logger.exception(
        "Unhandled error on %s %s",
        request.method,
        request.url.path
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error"
        }
    )

@app.get("/test-error")
def test_error():
    raise Exception("Testing global exception handler")

Base.metadata.create_all(bind=engine)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message": "ExpenseIQ is alive"
    }


# =========================================================
# SIGNUP
# =========================================================

@app.post("/signup", response_model=schemas.UserResponse)
def signup(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_pw = hash_password(user.password)

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pw
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info("New user registered")

    return new_user


# =========================================================
# LOGIN
# =========================================================

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # print(">>>> LOGIN ENDPOINT REACHED <<<<")
    logger.info("Login attempt")

    db_user = db.query(models.User).filter(
        models.User.email == form_data.username
    ).first()

    if not db_user:
        logger.warning("Login failed: user not found")

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        form_data.password,
        db_user.hashed_password
    ):
        logger.warning("Login failed: incorrect password")

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = create_access_token(
        data={"sub": db_user.email}
    )

    logger.info("User logged in successfully")

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# =========================================================
# CURRENT USER
# =========================================================

@app.get("/me", response_model=schemas.UserResponse)
def get_me(
    current_user: models.User = Depends(get_current_user)
):
    return current_user


# =========================================================
# CREATE EXPENSE
# =========================================================

@app.post(
    "/expenses",
    response_model=schemas.ExpenseResponse
)
def create_expense(
    expense: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_expense = models.Expense(
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        user_id=current_user.id
    )

    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)

    logger.info("Expense created successfully")

    return db_expense


# =========================================================
# GET EXPENSES
# Filtering + Search + Sorting + Pagination
# =========================================================

@app.get("/expenses")
def get_expenses(
    category: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    search: str | None = None,
    sort: str | None = None,

    skip: int = Query(
        default=0,
        ge=0
    ),

    limit: int = Query(
        default=10,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Only logged-in user's expenses
    query = db.query(models.Expense).filter(
        models.Expense.user_id == current_user.id
    )

    # Category filter
    if category:
        query = query.filter(
            models.Expense.category == category
        )

    # Minimum amount
    if min_amount is not None:
        query = query.filter(
            models.Expense.amount >= min_amount
        )

    # Maximum amount
    if max_amount is not None:
        query = query.filter(
            models.Expense.amount <= max_amount
        )

    # Search description
    if search:
        query = query.filter(
            models.Expense.description.ilike(
                f"%{search}%"
            )
        )

    # Sorting
    if sort == "highest":
        query = query.order_by(
            models.Expense.amount.desc()
        )

    elif sort == "lowest":
        query = query.order_by(
            models.Expense.amount.asc()
        )

    elif sort == "newest":
        query = query.order_by(
            models.Expense.created_at.desc()
        )

    elif sort == "oldest":
        query = query.order_by(
            models.Expense.created_at.asc()
        )

    else:
        # Default: newest expenses first
        query = query.order_by(
            models.Expense.created_at.desc()
        )

    # Count BEFORE pagination
    total = query.count()

    # Pagination
    expenses = (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "count": len(expenses),
        "data": expenses
    }


# =========================================================
# TOTAL EXPENSE SUMMARY
# =========================================================

@app.get("/expenses/summary")
def expense_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    total = db.query(
        func.sum(models.Expense.amount)
    ).filter(
        models.Expense.user_id == current_user.id
    ).scalar()

    return {
        "total_expenses": total or 0
    }


# =========================================================
# CATEGORY SUMMARY
# =========================================================

@app.get("/expenses/summary/categories")
def category_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    results = db.query(
        models.Expense.category,
        func.sum(models.Expense.amount)
    ).filter(
        models.Expense.user_id == current_user.id
    ).group_by(
        models.Expense.category
    ).all()

    return {
        category: total
        for category, total in results
    }


# =========================================================
# HIGHEST EXPENSE
# =========================================================

@app.get("/expenses/summary/highest")
def highest_expense(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    expense = db.query(
        models.Expense
    ).filter(
        models.Expense.user_id == current_user.id
    ).order_by(
        models.Expense.amount.desc()
    ).first()

    if expense is None:
        return {
            "message": "No expenses found"
        }

    return {
        "id": expense.id,
        "description": expense.description,
        "amount": expense.amount,
        "category": expense.category,
        "created_at": expense.created_at
    }


# =========================================================
# MONTHLY SUMMARY
# =========================================================

@app.get("/expenses/summary/monthly")
def monthly_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    results = db.query(
        func.extract(
            "year",
            models.Expense.created_at
        ).label("year"),

        func.extract(
            "month",
            models.Expense.created_at
        ).label("month"),

        func.sum(
            models.Expense.amount
        ).label("total")
    ).filter(
        models.Expense.user_id == current_user.id
    ).group_by(
        func.extract(
            "year",
            models.Expense.created_at
        ),
        func.extract(
            "month",
            models.Expense.created_at
        )
    ).order_by(
        func.extract(
            "year",
            models.Expense.created_at
        ),
        func.extract(
            "month",
            models.Expense.created_at
        )
    ).all()

    return [
        {
            "year": int(year),
            "month": int(month),
            "total": total
        }
        for year, month, total in results
    ]


# =========================================================
# CURRENT MONTH SUMMARY
# =========================================================

@app.get("/expenses/summary/current-month")
def current_month_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)

    total = db.query(
        func.sum(models.Expense.amount)
    ).filter(
        models.Expense.user_id == current_user.id,

        func.extract(
            "year",
            models.Expense.created_at
        ) == now.year,

        func.extract(
            "month",
            models.Expense.created_at
        ) == now.month
    ).scalar()

    return {
        "year": now.year,
        "month": now.month,
        "total": total or 0
    }


# =========================================================
# GET SINGLE EXPENSE
# IMPORTANT: Keep after /summary routes
# =========================================================

@app.get(
    "/expenses/{expense_id}",
    response_model=schemas.ExpenseResponse
)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    expense = db.query(
        models.Expense
    ).filter(
        models.Expense.id == expense_id,
        models.Expense.user_id == current_user.id
    ).first()

    if expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    return expense


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Total spending
    total = db.query(
        func.sum(models.Expense.amount)
    ).filter(
        models.Expense.user_id == current_user.id
    ).scalar()

    # Current month
    now = datetime.now(timezone.utc)

    current_month_total = db.query(
        func.sum(models.Expense.amount)
    ).filter(
        models.Expense.user_id == current_user.id,

        func.extract(
            "year",
            models.Expense.created_at
        ) == now.year,

        func.extract(
            "month",
            models.Expense.created_at
        ) == now.month
    ).scalar()

    # Highest expense
    highest = db.query(
        models.Expense
    ).filter(
        models.Expense.user_id == current_user.id
    ).order_by(
        models.Expense.amount.desc()
    ).first()

    # Category totals
    category_results = db.query(
        models.Expense.category,
        func.sum(models.Expense.amount)
    ).filter(
        models.Expense.user_id == current_user.id
    ).group_by(
        models.Expense.category
    ).all()

    return {
        "total_expenses": total or 0,

        "current_month": current_month_total or 0,

        "highest_expense": {
            "description": highest.description,
            "amount": highest.amount,
            "category": highest.category,
            "created_at": highest.created_at
        } if highest else None,

        "categories": {
            category: amount
            for category, amount in category_results
        }
    }


# =========================================================
# UPDATE EXPENSE - PUT
# =========================================================

@app.put(
    "/expenses/{expense_id}",
    response_model=schemas.ExpenseResponse
)
def update_expense(
    expense_id: int,
    updated_expense: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    expense = db.query(
        models.Expense
    ).filter(
        models.Expense.id == expense_id,
        models.Expense.user_id == current_user.id
    ).first()

    if expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    expense.description = updated_expense.description
    expense.amount = updated_expense.amount
    expense.category = updated_expense.category

    db.commit()
    db.refresh(expense)

    logger.info("Expense updated successfully")

    return expense


# =========================================================
# PARTIAL UPDATE - PATCH
# =========================================================

@app.patch(
    "/expenses/{expense_id}",
    response_model=schemas.ExpenseResponse
)
def patch_expense(
    expense_id: int,
    updated_expense: schemas.ExpensePatch,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    expense = db.query(
        models.Expense
    ).filter(
        models.Expense.id == expense_id,
        models.Expense.user_id == current_user.id
    ).first()

    if expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    update_data = updated_expense.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)

    logger.info("Expense partially updated successfully")

    return expense


# =========================================================
# DELETE EXPENSE
# =========================================================

@app.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    expense = db.query(
        models.Expense
    ).filter(
        models.Expense.id == expense_id,
        models.Expense.user_id == current_user.id
    ).first()

    if expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    db.delete(expense)
    db.commit()

    logger.info("Expense deleted successfully")

    return {
        "message": "Expense deleted successfully"
    }