"""Pairing card widget builder.

Constructs pairing card widgets from PairingCardData objects,
delegating button actions to callback functions.
"""

from typing import Protocol

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.presenters.round_view_presenter import PairingCardData
from gui.styles import (
    BUTTON_SECONDARY_STYLE,
    create_card_style_from_data,
    create_status_text_from_data,
)


class PairingCallbacks(Protocol):
    """Callbacks for pairing card button actions."""

    def on_assign(self, pairing_id: int) -> None: ...
    def on_remove_assignment(self, pairing_id: int) -> None: ...
    def on_edit(self, pairing_id: int) -> None: ...
    def on_remove_pairing(self, pairing_id: int) -> None: ...
    def on_toggle_exclude(self, pairing_id: int) -> None: ...


class PairingCardBuilder:
    """Builds a pairing card widget from presenter data."""

    def build(self, card_data: PairingCardData, callbacks: PairingCallbacks) -> QWidget:
        """Build a complete pairing card widget."""
        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)

        self._add_title(layout, card_data)
        self._add_status(layout, card_data)
        self._add_stats(layout, card_data)
        self._add_controls(layout, card_data, callbacks)

        card.setStyleSheet(create_card_style_from_data(card_data))
        return card

    def _add_title(self, layout: QVBoxLayout, data: PairingCardData) -> None:
        """Add participant names to pairing card."""
        title = QLabel(f"{data.p1_name} vs {data.p2_name}")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

    def _add_status(self, layout: QVBoxLayout, data: PairingCardData) -> None:
        """Add assignment status to pairing card."""
        status_text = create_status_text_from_data(data)
        status = QLabel(status_text)
        status.setStyleSheet("font-size: 12px;")
        layout.addWidget(status)

    def _add_stats(self, layout: QVBoxLayout, data: PairingCardData) -> None:
        """Add digital round statistics to pairing card."""
        combined = QLabel(
            f"Combined digital rounds: "
            f"{data.p1_count} + {data.p2_count} = {data.combined_count}"
        )
        combined.setStyleSheet("font-size: 11px; color: #718096;")
        layout.addWidget(combined)

    def _add_controls(
        self, layout: QVBoxLayout, data: PairingCardData, callbacks: PairingCallbacks
    ) -> None:
        """Add control buttons to pairing card."""
        button_layout = QHBoxLayout()
        pairing_id = data.pairing.id

        if data.digital_label:
            self._add_remove_assignment_button(
                button_layout, pairing_id, callbacks.on_remove_assignment
            )
        else:
            self._add_assign_button(button_layout, pairing_id, callbacks.on_assign)

        self._add_edit_button(button_layout, pairing_id, callbacks.on_edit)
        self._add_remove_pairing_button(
            button_layout, pairing_id, callbacks.on_remove_pairing
        )
        self._add_toggle_button(
            button_layout, data.is_excluded, pairing_id, callbacks.on_toggle_exclude
        )

        layout.addLayout(button_layout)

    @staticmethod
    def _add_remove_assignment_button(
        layout: QHBoxLayout, pairing_id: int, callback
    ) -> None:
        btn = QPushButton("Remove Assignment")
        btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        btn.clicked.connect(lambda _, pid=pairing_id: callback(pid))
        layout.addWidget(btn)

    @staticmethod
    def _add_assign_button(layout: QHBoxLayout, pairing_id: int, callback) -> None:
        btn = QPushButton("Assign")
        btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        btn.clicked.connect(lambda _, pid=pairing_id: callback(pid))
        layout.addWidget(btn)

    @staticmethod
    def _add_edit_button(layout: QHBoxLayout, pairing_id: int, callback) -> None:
        btn = QPushButton("Edit")
        btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        btn.clicked.connect(lambda _, pid=pairing_id: callback(pid))
        layout.addWidget(btn)

    @staticmethod
    def _add_remove_pairing_button(
        layout: QHBoxLayout, pairing_id: int, callback
    ) -> None:
        btn = QPushButton("Remove Pairing")
        btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        btn.clicked.connect(lambda _, pid=pairing_id: callback(pid))
        layout.addWidget(btn)

    @staticmethod
    def _add_toggle_button(
        layout: QHBoxLayout, is_excluded: bool, pairing_id: int, callback
    ) -> None:
        text = "Include" if is_excluded else "Exclude"
        btn = QPushButton(text)
        btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        btn.clicked.connect(lambda _, pid=pairing_id: callback(pid))
        layout.addWidget(btn)
