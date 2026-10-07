from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import Order, User


def recent_paid(session: Session):
    # WHERE status = ? ORDER BY created_at DESC
    # -> orders(status, created_at) 인덱스 없음 -> missing_index + order_by_filesort
    orders = (
        session.query(Order)
        .filter(Order.status == "paid")
        .order_by(Order.created_at.desc())
        .all()
    )
    lines = []
    for o in orders:            # N+1: o.user 접근(lazy="select")인데 selectinload/joinedload 누락
        lines.append(o.user.name)
    return lines


def search_by_name(session: Session, q: str):
    # name.ilike('%q%') -> LIKE '%q%' (선행 와일드카드) -> leading_wildcard_like
    return session.query(User).filter(User.name.ilike(f"%{q}%")).all()


def paid_orders_20(session: Session):
    # 2.0 스타일 select(); FK 조인(user_id)에 인덱스 없음 -> missing_index 대상
    stmt = select(Order).where(Order.status == "paid").limit(20)
    return session.execute(stmt).scalars().all()


def unsafe_search(session: Session, name: str):
    # f-string 보간 -> string_substitution(SQL 인젝션 + 플랜 캐시 오염) + SELECT * -> select_star
    # 안전: text("SELECT id, name FROM users WHERE name = :n").bindparams(n=name)
    return session.execute(text(f"SELECT * FROM users WHERE name = '{name}'")).all()
