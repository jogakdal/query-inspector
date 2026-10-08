from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    # SQLAlchemy는 FK에 자동 인덱스를 만들지 않는다(Django와 반대).
    # user_id에 index=True가 없으므로, FK 조인/필터 시 missing_index 대상이다.
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20))
    created_at = Column(DateTime)
    # (status, created_at) 복합 인덱스 없음 -> 아래 쿼리에서 missing_index.

    # lazy="select"(기본): 반복에서 o.user 접근 시 지연 SELECT -> N+1.
    user = relationship("User")
