"""Allocation presenter - handles digital board allocation logic."""
from typing import Callable

from PyQt6.QtWidgets import QMessageBox, QInputDialog
from sqlalchemy.orm import Session

from database import get_digital_assignment
from logic import (
    allocate_digital_boards,
    clear_round_assignments,
    exclude_from_digital,
    generate_digital_board_labels,
    manually_assign_digital_board,
)


class AllocationPresenter:
    """Handles digital board allocation logic.

    Separates allocation orchestration from GUI concerns.
    """

    def __init__(
        self,
        session: Session,
        tournament_id: int,
        num_digital_boards: int,
        on_allocated: Callable[[int], None],
        on_cleared: Callable[[int], None],
        on_assignment_changed: Callable[[], None],
    ):
        self.session = session
        self.tournament_id = tournament_id
        self.num_digital_boards = num_digital_boards
        self.on_allocated = on_allocated
        self.on_cleared = on_cleared
        self.on_assignment_changed = on_assignment_changed

    def allocate_round(self, round_id: int, parent_widget) -> None:
        """Allocate digital boards for a round.

        Returns the number of boards allocated, or 0 if cancelled.
        """
        try:
            result = allocate_digital_boards(
                self.session, round_id, self.num_digital_boards
            )
            self.on_allocated(len(result))
            self.on_assignment_changed()
            QMessageBox.information(
                parent_widget,
                "Success",
                f"Allocated {len(result)} digital board(s)",
            )
        except Exception as e:
            QMessageBox.critical(parent_widget, "Error", f"Failed to allocate: {e}")

    def clear_round(self, round_id: int, parent_widget) -> int:
        """Clear all digital board assignments for a round.

        Returns the number of assignments cleared, or 0 if cancelled.
        """
        reply = QMessageBox.question(
            parent_widget,
            "Confirm",
            "Clear all digital board assignments for this round?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return 0

        try:
            count = clear_round_assignments(self.session, round_id)
            self.on_cleared(count)
            self.on_assignment_changed()
            QMessageBox.information(
                parent_widget, "Success", f"Cleared {count} assignment(s)"
            )
            return count
        except Exception as e:
            QMessageBox.critical(parent_widget, "Error", f"Failed to clear: {e}")
            return 0

    def manual_assign(self, pairing_id: int, parent_widget) -> None:
        """Manually assign a digital board to a pairing."""
        labels = generate_digital_board_labels(self.num_digital_boards)

        selected, ok = QInputDialog.getItem(
            parent_widget,
            "Assign Digital Board",
            "Choose a digital board:",
            labels,
            0,
            False,
        )

        if ok:
            try:
                manually_assign_digital_board(self.session, pairing_id, selected)
                self.on_assignment_changed()
            except Exception as e:
                QMessageBox.critical(
                    parent_widget, "Error", f"Failed to assign: {e}"
                )

    def remove_assignment(self, pairing_id: int, parent_widget) -> None:
        """Remove digital board assignment from a pairing."""
        try:
            manually_assign_digital_board(self.session, pairing_id, None)
            self.on_assignment_changed()
        except Exception as e:
            QMessageBox.critical(
                parent_widget, "Error", f"Failed to remove: {e}"
            )

    def toggle_exclude(self, pairing_id: int, parent_widget) -> None:
        """Toggle exclude/include status for a pairing."""
        assignment = get_digital_assignment(self.session, pairing_id)
        excluded = not (assignment and assignment.is_excluded)

        try:
            exclude_from_digital(self.session, pairing_id, excluded)
            self.on_assignment_changed()
        except Exception as e:
            QMessageBox.critical(parent_widget, "Error", f"Failed to toggle: {e}")
