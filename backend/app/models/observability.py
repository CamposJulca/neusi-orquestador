from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class ObservabilitySnapshot(Base):
    __tablename__ = "observability_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    server_code = Column(String(16), index=True, nullable=False)
    snapshot_type = Column(String(32), default="auto", nullable=False)
    status = Column(String(16), nullable=False)
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
