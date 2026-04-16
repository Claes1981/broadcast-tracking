import csv
import json
from pathlib import Path
from sqlalchemy.orm import Session

from database.models import Round, Pairing, DigitalAssignment
from database.queries import get_tournament, get_all_rounds, get_all_participants


def export_to_csv(session: Session, tournament_id: int, output_path: str) -> Path:
    """
    Export tournament digital board assignments to CSV.

    Args:
        session: Database session
        tournament_id: ID of the tournament to export
        output_path: Path to save the CSV file

    Returns:
        Path to the created CSV file
    """
    tournament = get_tournament(session, tournament_id)
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    rounds = get_all_rounds(session, tournament_id)

    # Ensure directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle filename collision
    if output_path.exists():
        output_path = _get_unique_filename(output_path)

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Header
        writer.writerow(
            [
                "Tournament",
                "Round",
                "Board",
                "Participant 1",
                "Participant 2",
                "Assignment Type",
                "Board Number",
            ]
        )

        # Data rows
        for round_obj in sorted(rounds, key=lambda r: r.round_number):
            pairings = [p for p in round_obj.pairings if p.digital_assignment]

            for pairing in pairings:
                assignment = pairing.digital_assignment
                if assignment.digital_board_label:
                    writer.writerow(
                        [
                            tournament.name,
                            round_obj.round_number,
                            assignment.digital_board_label,
                            pairing.participant1.name,
                            pairing.participant2.name,
                            "Manual" if assignment.is_manual else "Auto",
                            pairing.board_number or "",
                        ]
                    )

    return output_path


def export_to_json(session: Session, tournament_id: int, output_path: str) -> Path:
    """
    Export tournament digital board assignments to JSON.

    Args:
        session: Database session
        tournament_id: ID of the tournament to export
        output_path: Path to save the JSON file

    Returns:
        Path to the created JSON file
    """
    tournament = get_tournament(session, tournament_id)
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    rounds = get_all_rounds(session, tournament_id)

    # Build data structure
    data = {
        "tournament": {
            "id": tournament.id,
            "name": tournament.name,
            "tournament_type": tournament.tournament_type,
            "source_url": tournament.source_url,
            "created_at": tournament.created_at.isoformat()
            if tournament.created_at
            else None,
        },
        "rounds": [],
    }

    for round_obj in sorted(rounds, key=lambda r: r.round_number):
        round_data = {
            "round_number": round_obj.round_number,
            "fetched_at": round_obj.fetched_at.isoformat()
            if round_obj.fetched_at
            else None,
            "pairings": [],
        }

        for pairing in round_obj.pairings:
            pairing_data = {
                "participant1": pairing.participant1.name,
                "participant2": pairing.participant2.name,
                "board_number": pairing.board_number,
                "score1": pairing.score1,
                "score2": pairing.score2,
                "digital_board": None,
            }

            if pairing.digital_assignment:
                pairing_data["digital_board"] = {
                    "label": pairing.digital_assignment.digital_board_label,
                    "is_manual": pairing.digital_assignment.is_manual,
                    "is_excluded": pairing.digital_assignment.is_excluded,
                    "created_at": pairing.digital_assignment.created_at.isoformat()
                    if pairing.digital_assignment.created_at
                    else None,
                }

            round_data["pairings"].append(pairing_data)

        data["rounds"].append(round_data)

    # Ensure directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle filename collision
    if output_path.exists():
        output_path = _get_unique_filename(output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return output_path


def export_statistics(session: Session, tournament_id: int, output_path: str) -> Path:
    """
    Export digital board usage statistics to CSV.

    Args:
        session: Database session
        tournament_id: ID of the tournament to export
        output_path: Path to save the CSV file

    Returns:
        Path to the created CSV file
    """
    tournament = get_tournament(session, tournament_id)
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    participants = get_all_participants(session, tournament_id)
    rounds = get_all_rounds(session, tournament_id)

    from database.queries import count_digital_rounds_for_participant

    stats = []
    for participant in participants:
        count = count_digital_rounds_for_participant(session, participant.id)
        stats.append(
            {
                "participant": participant.name,
                "digital_rounds": count,
                "total_rounds": len(rounds),
            }
        )

    # Sort by digital rounds descending
    stats.sort(key=lambda x: x["digital_rounds"], reverse=True)

    # Ensure directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle filename collision
    if output_path.exists():
        output_path = _get_unique_filename(output_path)

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=["participant", "digital_rounds", "total_rounds"]
        )
        writer.writeheader()
        writer.writerows(stats)

    return output_path


def _get_unique_filename(path: Path) -> Path:
    """
    Generate a unique filename by appending a counter if file exists.

    Args:
        path: Original path

    Returns:
        Path with unique filename
    """
    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    new_path = parent / f"{stem}_{counter}{suffix}"

    while new_path.exists():
        counter += 1
        new_path = parent / f"{stem}_{counter}{suffix}"

    return new_path
