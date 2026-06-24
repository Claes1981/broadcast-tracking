"""Export utilities for tournament data."""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Final

from sqlalchemy.orm import Session

from database.models import Round, Tournament
from database.queries import (
    get_tournament,
    get_all_rounds,
    get_all_participants,
    count_digital_rounds_for_participant,
)


class Exporter(ABC):
    """Strategy interface for tournament data exporters."""

    @abstractmethod
    def export(self, session: Session, tournament_id: int, output_path: str) -> Path:
        """Export tournament data and return the output path."""
        ...


def _prepare_export(
    session: Session, tournament_id: int, output_path: str
) -> tuple[Tournament, list[Round], Path]:
    """Common export preparation: validate tournament, load rounds, resolve path."""
    tournament = get_tournament(session, tournament_id)
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    rounds = get_all_rounds(session, tournament_id)

    resolved_path = Path(output_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_path.exists():
        resolved_path = _get_unique_filename(resolved_path)

    return tournament, rounds, resolved_path


class CsvExporter(Exporter):
    """Export tournament digital board assignments to CSV."""

    def export(self, session: Session, tournament_id: int, output_path: str) -> Path:
        tournament, rounds, resolved_path = _prepare_export(
            session, tournament_id, output_path
        )

        with open(resolved_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
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

        return resolved_path


class JsonExporter(Exporter):
    """Export tournament digital board assignments to JSON."""

    def export(self, session: Session, tournament_id: int, output_path: str) -> Path:
        tournament, rounds, resolved_path = _prepare_export(
            session, tournament_id, output_path
        )

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

        with open(resolved_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return resolved_path


class StatisticsExporter(Exporter):
    """Export digital board usage statistics to CSV."""

    def export(self, session: Session, tournament_id: int, output_path: str) -> Path:
        tournament, rounds, resolved_path = _prepare_export(
            session, tournament_id, output_path
        )
        participants = get_all_participants(session, tournament_id)

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

        stats.sort(key=lambda x: x["digital_rounds"], reverse=True)

        with open(resolved_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=["participant", "digital_rounds", "total_rounds"]
            )
            writer.writeheader()
            writer.writerows(stats)

        return resolved_path


# Registry of exporters by format name
EXPORTERS: Final[dict[str, Exporter]] = {
    "CSV": CsvExporter(),
    "JSON": JsonExporter(),
    "Statistics": StatisticsExporter(),
}


def export(
    session: Session, tournament_id: int, output_path: str, format_type: str
) -> Path:
    """
    Export tournament data using the strategy pattern.

    Args:
        session: Database session
        tournament_id: ID of the tournament to export
        output_path: Path to save the output file
        format_type: Export format ("CSV", "JSON", or "Statistics")

    Returns:
        Path to the created file

    Raises:
        ValueError: If format_type is not recognized
    """
    exporter = EXPORTERS.get(format_type)
    if exporter is None:
        raise ValueError(
            f"Unknown export format: {format_type!r}. "
            f"Supported: {list(EXPORTERS.keys())}"
        )
    return exporter.export(session, tournament_id, output_path)


# Backward-compatible wrappers
def export_to_csv(session: Session, tournament_id: int, output_path: str) -> Path:
    """Export tournament data to CSV (backward-compatible wrapper)."""
    return export(session, tournament_id, output_path, "CSV")


def export_to_json(session: Session, tournament_id: int, output_path: str) -> Path:
    """Export tournament data to JSON (backward-compatible wrapper)."""
    return export(session, tournament_id, output_path, "JSON")


def export_statistics(session: Session, tournament_id: int, output_path: str) -> Path:
    """Export digital board statistics to CSV (backward-compatible wrapper)."""
    return export(session, tournament_id, output_path, "Statistics")


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
