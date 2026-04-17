import random
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from database.models import Pairing, DigitalAssignment
from database.queries import get_pairing_digital_sum, get_round_pairings


def generate_digital_board_labels(num_boards: int, prefix: str = "Board") -> List[str]:
    """Generate labels like 'Board A', 'Board B', 'Board C'..."""
    labels = []
    for i in range(num_boards):
        letter = chr(ord("A") + i)
        labels.append(f"{prefix} {letter}")
    return labels


def allocate_digital_boards(
    session: Session, round_id: int, num_digital_boards: int, prefix: str = "Board"
) -> List[Tuple[Pairing, str]]:
    """
    Allocate digital boards for a round.

    Algorithm:
    1. Get all pairings for the round (excluding byes - pairings where either participant is None)
    2. For each pairing, calculate: digital_count(p1) + digital_count(p2)
    3. Sort pairings by combined count (ascending)
    4. Take top N pairings where N = num_digital_boards
    5. If ties at the cutoff, randomly select among tied pairings
    6. Assign digital board labels
    7. Return list of (pairing, label) tuples

    Returns: List of (Pairing, digital_board_label) tuples for assigned pairings
    """
    pairings = get_round_pairings(session, round_id)

    if not pairings:
        return []

    digital_labels = generate_digital_board_labels(num_digital_boards, prefix)

    pairing_sums = []
    for pairing in pairings:
        digital_sum = get_pairing_digital_sum(session, pairing)
        pairing_sums.append((pairing, digital_sum))

    pairing_sums.sort(key=lambda x: x[1])

    if num_digital_boards >= len(pairing_sums):
        result = []
        for i, (pairing, _) in enumerate(pairing_sums):
            existing = (
                session.query(DigitalAssignment)
                .filter(DigitalAssignment.pairing_id == pairing.id)
                .first()
            )
            if existing and existing.is_manual:
                continue
            if existing:
                session.delete(existing)
            label = digital_labels[i] if i < len(digital_labels) else None
            assignment = DigitalAssignment(
                pairing_id=pairing.id,
                digital_board_label=label,
                is_manual=False,
                is_excluded=False,
            )
            session.add(assignment)
            if label:
                result.append((pairing, label))
        session.commit()
        return result

    cutoff_index = num_digital_boards - 1
    cutoff_sum = pairing_sums[cutoff_index][1]

    tied_pairings = [(p, s) for p, s in pairing_sums if s == cutoff_sum]
    before_cutoff = [(p, s) for p, s in pairing_sums if s < cutoff_sum]

    num_to_select_from_tied = num_digital_boards - len(before_cutoff)
    selected_tied = (
        random.sample(tied_pairings, num_to_select_from_tied)
        if num_to_select_from_tied <= len(tied_pairings)
        else tied_pairings
    )

    selected_pairings = before_cutoff + selected_tied
    selected_pairings.sort(key=lambda x: x[1])

    assignments_to_clear = set()
    for pairing, _ in selected_pairings:
        existing = (
            session.query(DigitalAssignment)
            .filter(DigitalAssignment.pairing_id == pairing.id)
            .first()
        )
        if existing and existing.is_manual:
            continue
        if existing:
            assignments_to_clear.add(existing.id)

    for assignment_id in assignments_to_clear:
        session.query(DigitalAssignment).filter(
            DigitalAssignment.id == assignment_id
        ).delete()

    result = []
    for i, (pairing, _) in enumerate(selected_pairings):
        label = digital_labels[i]
        assignment = DigitalAssignment(
            pairing_id=pairing.id,
            digital_board_label=label,
            is_manual=False,
            is_excluded=False,
        )
        session.add(assignment)
        result.append((pairing, label))

    session.commit()
    return result


def clear_round_assignments(session: Session, round_id: int) -> int:
    """
    Clear all digital board assignments for a round.
    Returns the number of assignments cleared.
    """
    pairings = get_round_pairings(session, round_id)
    count = 0
    for pairing in pairings:
        assignment = (
            session.query(DigitalAssignment)
            .filter(DigitalAssignment.pairing_id == pairing.id)
            .first()
        )
        if assignment:
            session.delete(assignment)
            count += 1
    session.commit()
    return count


def manually_assign_digital_board(
    session: Session, pairing_id: int, digital_board_label: Optional[str]
) -> DigitalAssignment:
    """
    Manually assign or remove a digital board for a pairing.
    If digital_board_label is None, removes the assignment.
    """
    assignment = (
        session.query(DigitalAssignment)
        .filter(DigitalAssignment.pairing_id == pairing_id)
        .first()
    )

    if assignment:
        assignment.digital_board_label = digital_board_label
        assignment.is_manual = True
        assignment.is_excluded = False
    else:
        assignment = DigitalAssignment(
            pairing_id=pairing_id,
            digital_board_label=digital_board_label,
            is_manual=True,
            is_excluded=False,
        )
        session.add(assignment)

    session.commit()
    return assignment


def exclude_from_digital(
    session: Session, pairing_id: int, excluded: bool
) -> DigitalAssignment:
    """
    Manually exclude or include a pairing from digital board consideration.
    """
    assignment = (
        session.query(DigitalAssignment)
        .filter(DigitalAssignment.pairing_id == pairing_id)
        .first()
    )

    if not assignment:
        assignment = DigitalAssignment(
            pairing_id=pairing_id,
            digital_board_label=None,
            is_manual=False,
            is_excluded=excluded,
        )
        session.add(assignment)
    else:
        assignment.is_excluded = excluded
        if excluded:
            assignment.digital_board_label = None

    session.commit()
    return assignment
