from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    source_url = Column(String)
    tournament_type = Column(String, default="individual")  # 'individual' or 'team'
    created_at = Column(DateTime, default=datetime.utcnow)
    db_file = Column(String, unique=True)

    rounds = relationship(
        "Round", back_populates="tournament", cascade="all, delete-orphan"
    )
    participants = relationship(
        "Participant", back_populates="tournament", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Tournament(id={self.id}, name='{self.name}')>"


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    name = Column(String, nullable=False)
    participant_type = Column(String, default="player")  # 'player' or 'team'

    tournament = relationship("Tournament", back_populates="participants")
    pairings_as_p1 = relationship(
        "Pairing", foreign_keys="Pairing.participant1_id", back_populates="participant1"
    )
    pairings_as_p2 = relationship(
        "Pairing", foreign_keys="Pairing.participant2_id", back_populates="participant2"
    )

    __table_args__ = (
        UniqueConstraint("tournament_id", "name", name="uq_tournament_participant"),
    )

    def __repr__(self):
        return f"<Participant(id={self.id}, name='{self.name}')>"


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    fetched_at = Column(DateTime)
    pairings_html = Column(Text)

    tournament = relationship("Tournament", back_populates="rounds")
    pairings = relationship(
        "Pairing", back_populates="round", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tournament_id", "round_number", name="uq_tournament_round"),
    )

    def __repr__(self):
        return f"<Round(id={self.id}, tournament_id={self.tournament_id}, round_number={self.round_number})>"


class Pairing(Base):
    __tablename__ = "pairings"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    participant1_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    participant2_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    board_number = Column(Integer)
    score1 = Column(Float)
    score2 = Column(Float)

    round = relationship("Round", back_populates="pairings")
    participant1 = relationship(
        "Participant", foreign_keys=[participant1_id], back_populates="pairings_as_p1"
    )
    participant2 = relationship(
        "Participant", foreign_keys=[participant2_id], back_populates="pairings_as_p2"
    )
    digital_assignment = relationship(
        "DigitalAssignment",
        uselist=False,
        back_populates="pairing",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Pairing(id={self.id}, round_id={self.round_id}, p1_id={self.participant1_id}, p2_id={self.participant2_id})>"


class DigitalAssignment(Base):
    __tablename__ = "digital_assignments"

    id = Column(Integer, primary_key=True)
    pairing_id = Column(Integer, ForeignKey("pairings.id"), nullable=False, unique=True)
    digital_board_label = Column(String, nullable=True)  # e.g., "Board A", "Board B"
    is_manual = Column(Boolean, default=False)
    is_excluded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pairing = relationship("Pairing", back_populates="digital_assignment")

    def __repr__(self):
        return f"<DigitalAssignment(id={self.id}, pairing_id={self.pairing_id}, board='{self.digital_board_label}')>"
