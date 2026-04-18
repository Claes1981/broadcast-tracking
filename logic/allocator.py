import random
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from database.models import Pairing, DigitalAssignment
from database.queries import get_pairing_digital_sum, get_round_pairings


def generate_digital_board_labels(num_boards: int, prefix: str = "Board") -> List[str]:
    """Generate labels like 'Board A', 'Board B', 'Board C'..."""
    if num_boards <= 0:
        return []

    labels = []
    for i in range(num_boards):
        letter = chr(ord("A") + i)
        labels.append(f"{prefix} {letter}")
    return labels


def _validate_allocation_params(num_boards: int, prefix: str) -> None:
    """Validate allocation parameters."""
    if num_boards < 0:
        raise ValueError("Number of boards cannot be negative")
    if not prefix or not prefix.strip():
        raise ValueError("Prefix cannot be empty")


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
    _validate_allocation_params(num_digital_boards, prefix)

    pairings = get_round_pairings(session, round_id)

    if not pairings:
        return []

    digital_labels = generate_digital_board_labels(num_digital_boards, prefix)
    pairing_sums = _calculate_pairing_digital_sums(session, pairings)
    pairing_sums.sort(key=lambda x: x[1])

    if num_digital_boards >= len(pairing_sums):
        return _allocate_all_pairings(session, pairing_sums, digital_labels)

    selected_pairings = _select_pairings_with_tiebreaking(
        pairing_sums, num_digital_boards
    )
    return _assign_digital_boards(session, selected_pairings, digital_labels)


def _calculate_pairing_digital_sums(
    session: Session, pairings: List[Pairing]
) -> List[Tuple[Pairing, int]]:
    """Calculate digital round sums for all pairings."""
    pairing_sums = []
    for pairing in pairings:
        digital_sum = get_pairing_digital_sum(session, pairing)
        pairing_sums.append((pairing, digital_sum))
    return pairing_sums


def _allocate_all_pairings(
    session: Session, pairing_sums: List[Tuple[Pairing, int]], digital_labels: List[str]
) -> List[Tuple[Pairing, str]]:
    """Allocate digital boards to all pairings when boards >= pairings."""
    result = []
    for i, (pairing, _) in enumerate(pairing_sums):
        existing = _get_existing_assignment(session, pairing.id)

        if existing and existing.is_manual:
            if existing.digital_board_label:
                result.append((pairing, existing.digital_board_label))
            continue

        if existing:
            session.delete(existing)

        label = digital_labels[i] if i < len(digital_labels) else None
        assignment = _create_assignment(pairing.id, label, False, False)
        session.add(assignment)

        if label:
            result.append((pairing, label))

    session.commit()
    return result


def _select_pairings_with_tiebreaking(
    pairing_sums: List[Tuple[Pairing, int]], num_digital_boards: int
) -> List[Tuple[Pairing, int]]:
    """Select pairings for allocation with random tiebreaking."""
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

    return selected_pairings


def _assign_digital_boards(
    session: Session,
    selected_pairings: List[Tuple[Pairing, int]],
    digital_labels: List[str],
) -> List[Tuple[Pairing, str]]:
    """Assign digital boards to selected pairings."""
    _clear_non_manual_assignments(session, selected_pairings)

    result = []
    for i, (pairing, _) in enumerate(selected_pairings):
        existing = _get_existing_assignment(session, pairing.id)

        if existing and existing.is_manual:
            if existing.digital_board_label:
                result.append((pairing, existing.digital_board_label))
            continue

        label = digital_labels[i]
        assignment = _create_assignment(pairing.id, label, False, False)
        session.add(assignment)
        result.append((pairing, label))

    session.commit()
    return result


def _get_existing_assignment(
    session: Session, pairing_id: int
) -> Optional[DigitalAssignment]:
    """Get existing digital assignment for a pairing."""
    return (
        session.query(DigitalAssignment)
        .filter(DigitalAssignment.pairing_id == pairing_id)
        .first()
    )


def _create_assignment(
    pairing_id: int, label: Optional[str], is_manual: bool, is_excluded: bool
) -> DigitalAssignment:
    """Create a new digital assignment."""
    return DigitalAssignment(
        pairing_id=pairing_id,
        digital_board_label=label,
        is_manual=is_manual,
        is_excluded=is_excluded,
    )


def _clear_non_manual_assignments(
    session: Session, selected_pairings: List[Tuple[Pairing, int]]
):
    """Clear non-manual assignments for selected pairings."""
    assignments_to_clear = set()
    for pairing, _ in selected_pairings:
        existing = _get_existing_assignment(session, pairing.id)
        if existing and existing.is_manual:
            continue
        if existing:
            assignments_to_clear.add(existing.id)

    for assignment_id in assignments_to_clear:
        session.query(DigitalAssignment).filter(
            DigitalAssignment.id == assignment_id
        ).delete()


def clear_round_assignments(session: Session, round_id: int) -> int:
    """
    Clear all digital board assignments for a round.
    Returns the number of assignments cleared.
    """
    pairings = get_round_pairings(session, round_id)
    count = 0

    for pairing in pairings:
        assignment = _get_existing_assignment(session, pairing.id)
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
    assignment = _get_existing_assignment(session, pairing_id)

    if assignment:
        _update_assignment_to_manual(assignment, digital_board_label)
    else:
        assignment = _create_assignment(pairing_id, digital_board_label, True, False)
        session.add(assignment)

    session.commit()
    return assignment


def _update_assignment_to_manual(
    assignment: DigitalAssignment, digital_board_label: Optional[str]
):
    """Update an existing assignment to manual mode."""
    assignment.digital_board_label = digital_board_label
    assignment.is_manual = True
    assignment.is_excluded = False


def exclude_from_digital(
    session: Session, pairing_id: int, excluded: bool
) -> DigitalAssignment:
    """
    Manually exclude or include a pairing from digital board consideration.
    """
    assignment = _get_existing_assignment(session, pairing_id)

    if not assignment:
        assignment = _create_assignment(pairing_id, None, False, excluded)
        session.add(assignment)
    else:
        _update_exclusion_status(assignment, excluded)

    session.commit()
    return assignment


def _update_exclusion_status(assignment: DigitalAssignment, excluded: bool):
    """Update the exclusion status of an assignment."""
    assignment.is_excluded = excluded
    if excluded:
        assignment.digital_board_label = None
