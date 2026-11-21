from sqlalchemy import DDL, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, event, text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import DEFAULT_BUSINESS_ID, Base

# One installation serves one business by default. Every business-owned row
# (appointments, conversations, knowledge items) carries ``business_id`` and
# every admin lookup is scoped to the business stored in the signed admin
# session (see app/ownership.py). Messages are owned through their conversation.


class Business(Base):
    """Owner/tenant of appointments, conversations and knowledge items."""
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, default="My Business")
    # Relative path under <database folder>/uploads/, set via Admin -> Settings.
    logo_path = Column(String(255), nullable=True)
    # Length of new bookings in minutes (Admin -> Settings). Existing appointments keep
    # their own Appointment.duration_minutes, so changing this never moves old bookings.
    appointment_minutes = Column(Integer, nullable=False, default=60, server_default=text("60"))
    created_at = Column(DateTime, default=datetime.utcnow)


# A brand-new database always contains the default owning business, so rows
# created by the public chat/booking flow can reference it immediately.
event.listen(
    Business.__table__,
    "after_create",
    DDL(f"INSERT INTO businesses (id, name, created_at) VALUES ({DEFAULT_BUSINESS_ID}, 'My Business', CURRENT_TIMESTAMP)"),
)


def _business_fk():
    return Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        default=DEFAULT_BUSINESS_ID,
        server_default=text(str(DEFAULT_BUSINESS_ID)),
        index=True,
    )


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id = Column(Integer, primary_key=True)
    business_id = _business_fk()
    question = Column(String(500), nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100), default="general")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    business_id = _business_fk()
    channel = Column(String(50), default="web")  # web, whatsapp, call
    external_id = Column(String(200), nullable=True, index=True)
    visitor_token = Column(String(64), nullable=True, index=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    status = Column(String(50), default="active")  # active, escalated, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    appointments = relationship("Appointment", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_phone_time", "customer_phone", "appointment_time"),
    )

    id = Column(Integer, primary_key=True)
    business_id = _business_fk()
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(50), nullable=True)
    service = Column(String(200), nullable=True)
    appointment_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)  # stored per booking (copied from Business.appointment_minutes)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="confirmed")  # confirmed, cancelled, completed
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="appointments")

    @property
    def end_time(self):
        from datetime import timedelta
        return self.appointment_time + timedelta(minutes=self.duration_minutes or 60)
