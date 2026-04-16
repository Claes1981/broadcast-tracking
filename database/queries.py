from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Tournament, Participant, Round, Pairing, DigitalAssignment


def get_tournament(session: Session, tournament_id: int) -> Tournament:
    return session.query(Tournament).filter(Tournament.id == tournament_id).first()


def get_all_participants(session: Session, tournament_id: int) -> list[Participant]:
    return (
        session.query(Participant)
        .filter(Participant.tournament_id == tournament_id)
        .all()
    )


def get_participant_by_name(
    session: Session, tournament_id: int, name: str
) -> Participant:
    return (
        session.query(Participant)
        .filter(Participant.tournament_id == tournament_id, Participant.name == name)
        .first()
    )


def get_all_rounds(session: Session, tournament_id: int) -> list[Round]:
    return (
        session.query(Round)
        .filter(Round.tournament_id == tournament_id)
        .order_by(Round.round_number)
        .all()
    )


def get_round(session: Session, tournament_id: int, round_number: int) -> Round:
    return (
        session.query(Round)
        .filter(
            Round.tournament_id == tournament_id, Round.round_number == round_number
        )
        .first()
    )


def get_round_pairings(session: Session, round_id: int) -> list[Pairing]:
    return session.query(Pairing).filter(Pairing.round_id == round_id).all()


def get_digital_assignment(session: Session, pairing_id: int) -> DigitalAssignment:
    return (
        session.query(DigitalAssignment)
        .filter(DigitalAssignment.pairing_id == pairing_id)
        .first()
    )


def count_digital_rounds_for_participant(session: Session, participant_id: int) -> int:
    """Count how many rounds a participant has been assigned to digital boards."""
    return (
        session.query(func.count(DigitalAssignment.id))
        .join(Pairing)
        .filter(
            (
                (Pairing.participant1_id == participant_id)
                | (Pairing.participant2_id == participant_id)
            ),
            DigitalAssignment.digital_board_label.isnot(None),
            DigitalAssignment.is_excluded == False,
        )
        .scalar()
    )


def get_participant_digital_counts(
    session: Session, tournament_id: int
) -> dict[int, int]:
    """Get a dictionary of participant_id -> digital round count."""
    participants = get_all_participants(session, tournament_id)
    return {
        p.id: count_digital_rounds_for_participant(session, p.id) for p in participants
    }


def get_pairing_digital_sum(session: Session, pairing: Pairing) -> int:
    """Get the sum of digital rounds for both participants in a pairing."""
    count1 = count_digital_rounds_for_participant(session, pairing.participant1_id)
    count2 = count_digital_rounds_for_participant(session, pairing.participant2_id)
    return count1 + count2


def get_round_numbers(session: Session, tournament_id: int) -> list[int]:
    """Get list of round numbers for a tournament."""
    rounds = get_all_rounds(session, tournament_id)
    return [r.round_number for r in rounds]


def get_max_round(session: Session, tournament_id: int) -> int:
    """Get the maximum round number for a tournament."""
    rounds = get_all_rounds(session, tournament_id)
    if not rounds:
        return 0
    return max(r.round_number for r in rounds)
