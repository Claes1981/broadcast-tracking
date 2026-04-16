from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
import os
import re

from config import DATA_DIR
from database.models import Base, Tournament


def get_database_path(tournament_name: str) -> str:
    """Generate database path for a tournament with collision handling."""
    base_name = re.sub(r"[^\w\-_]", "_", tournament_name)
    db_file = f"{base_name}.sqlite"
    db_path = os.path.join(DATA_DIR, db_file)

    counter = 1
    while os.path.exists(db_path):
        db_file = f"{base_name}_{counter}.sqlite"
        db_path = os.path.join(DATA_DIR, db_file)
        counter += 1

    return db_path


def create_database(tournament_name: str) -> str:
    """Create a new database for a tournament and return the path."""
    db_path = get_database_path(tournament_name)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return db_path


def get_engine(db_path: str):
    """Get SQLAlchemy engine for existing database."""
    return create_engine(f"sqlite:///{db_path}", future=True)


def get_session(db_path: str) -> Session:
    """Get a new database session."""
    engine = get_engine(db_path)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    return SessionLocal()


def create_tournament(
    name: str, source_url: str = None, tournament_type: str = "individual"
) -> tuple[str, int]:
    """
    Create a new tournament and return (db_path, tournament_id).
    """
    db_path = create_database(name)
    session = get_session(db_path)

    try:
        tournament = Tournament(
            name=name,
            source_url=source_url,
            tournament_type=tournament_type,
            db_file=db_path,
        )
        session.add(tournament)
        session.commit()
        session.refresh(tournament)
        return db_path, tournament.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def open_tournament(db_path: str) -> tuple[Session, int]:
    """
    Open an existing tournament and return (session, tournament_id).
    """
    session = get_session(db_path)
    try:
        tournament = session.query(Tournament).first()
        if not tournament:
            raise ValueError("No tournament found in database")
        return session, tournament.id
    except Exception:
        session.close()
        raise
