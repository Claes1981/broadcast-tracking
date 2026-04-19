from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional

from database.models import Tournament, Participant, Round, Pairing
from database.queries import (
    get_tournament,
    get_all_participants,
    get_participant_by_name,
    get_all_rounds,
    get_round,
    get_max_round,
    get_round_pairings,
)
from logic.pairing import PairingData, RoundData


def ensure_participant_exists(
    session: Session, tournament_id: int, name: str, participant_type: str = "player"
) -> Participant:
    """Get or create a participant by name."""
    participant = get_participant_by_name(session, tournament_id, name)
    if not participant:
        participant = Participant(
            tournament_id=tournament_id, name=name, participant_type=participant_type
        )
        session.add(participant)
        session.commit()
    return participant


def create_round_from_data(
    session: Session,
    tournament_id: int,
    round_data: RoundData,
    participant_type: str = "player",
) -> Round:
    """Create a round and its pairings from RoundData."""
    round_obj = get_round(session, tournament_id, round_data.round_number)

    if round_obj:
        existing_pairings = get_round_pairings(session, round_obj.id)
        for pairing in existing_pairings:
            session.delete(pairing)
        session.commit()
    else:
        round_obj = Round(
            tournament_id=tournament_id,
            round_number=round_data.round_number,
            fetched_at=datetime.utcnow(),
        )
        session.add(round_obj)
        session.commit()

    for pairing_data in round_data.pairings:
        p1 = ensure_participant_exists(
            session, tournament_id, pairing_data.participant1_name, participant_type
        )
        p2 = ensure_participant_exists(
            session, tournament_id, pairing_data.participant2_name, participant_type
        )

        pairing = Pairing(
            round_id=round_obj.id,
            participant1_id=p1.id,
            participant2_id=p2.id,
            board_number=pairing_data.board_number,
            score1=pairing_data.score1,
            score2=pairing_data.score2,
        )
        session.add(pairing)

    session.commit()
    return round_obj


def import_rounds_from_data(
    session: Session,
    tournament_id: int,
    rounds: List[RoundData],
    participant_type: str = "player",
) -> List[Round]:
    """Import multiple rounds from RoundData."""
    created_rounds = []
    for round_data in rounds:
        round_obj = create_round_from_data(
            session, tournament_id, round_data, participant_type
        )
        created_rounds.append(round_obj)
    return created_rounds


def get_tournament_stats(session: Session, tournament_id: int) -> dict:
    """Get statistics for a tournament."""
    tournament = get_tournament(session, tournament_id)
    participants = get_all_participants(session, tournament_id)
    rounds = get_all_rounds(session, tournament_id)

    return {
        "name": tournament.name,
        "tournament_type": tournament.tournament_type,
        "source_url": tournament.source_url,
        "num_participants": len(participants),
        "num_rounds": len(rounds),
        "max_round": get_max_round(session, tournament_id),
    }


def delete_round(session: Session, round_id: int) -> bool:
    """Delete a round and all its pairings and assignments."""
    from database.models import DigitalAssignment

    round_obj = session.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        return False

    pairings = get_round_pairings(session, round_id)
    for pairing in pairings:
        assignment = (
            session.query(DigitalAssignment)
            .filter(DigitalAssignment.pairing_id == pairing.id)
            .first()
        )
        if assignment:
            session.delete(assignment)
        session.delete(pairing)

    session.delete(round_obj)
    session.commit()
    return True


def remove_pairing(session: Session, pairing_id: int) -> bool:
    """Remove a pairing from a round."""
    from database.models import DigitalAssignment

    pairing = session.query(Pairing).filter(Pairing.id == pairing_id).first()
    if not pairing:
        return False

    assignment = (
        session.query(DigitalAssignment)
        .filter(DigitalAssignment.pairing_id == pairing_id)
        .first()
    )
    if assignment:
        session.delete(assignment)
    session.delete(pairing)
    session.commit()
    return True


def edit_pairing(
    session: Session,
    pairing_id: int,
    new_participant1_name: str,
    new_participant2_name: str,
) -> bool:
    """Edit the participants of an existing pairing."""
    from database.models import DigitalAssignment

    pairing = session.query(Pairing).filter(Pairing.id == pairing_id).first()
    if not pairing:
        return False

    tournament_id = (
        session.query(Round.tournament_id)
        .filter(Round.id == pairing.round_id)
        .scalar()
    )

    p1 = get_participant_by_name(session, tournament_id, new_participant1_name)
    if not p1:
        p1 = Participant(
            tournament_id=tournament_id,
            name=new_participant1_name,
            participant_type="team",
        )
        session.add(p1)

    p2 = get_participant_by_name(session, tournament_id, new_participant2_name)
    if not p2:
        p2 = Participant(
            tournament_id=tournament_id,
            name=new_participant2_name,
            participant_type="team",
        )
        session.add(p2)

    pairing.participant1_id = p1.id
    pairing.participant2_id = p2.id
    session.commit()
    return True
