from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AgentCorrection(Base):
    __tablename__ = "agent_corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=True, index=True)
    intent = Column(Text, nullable=False)
    correction = Column(Text, nullable=False)
    promoted = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


def init_corrections_db():
    from pika.infra.db import get_engine

    Base.metadata.create_all(get_engine())
