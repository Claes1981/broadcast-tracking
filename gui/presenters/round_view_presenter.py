from typing import Optional

from sqlalchemy.orm import Session

from database import (
    get_all_participants,
    get_all_rounds,
    get_round,
    get_round_pairings,
    get_digital_assignment,
    count_digital_rounds_for_participant,
)
from database.models import Round, Pairing


class ParticipantRow:
    """Data class for a participant row in the participants table."""

    def __init__(
        self,
        rank: int,
        name: str,
        digital_count: int,
    ):
        self.rank = rank
        self.name = name
        self.digital_count = digital_count


class PairingCardData:
    """Data class for a pairing card."""

    def __init__(
        self,
        pairing: Pairing,
        p1_name: str,
        p2_name: str,
        digital_label: Optional[str],
        is_manual: bool,
        is_excluded: bool,
        has_assignment: bool,
        p1_count: int,
        p2_count: int,
        combined_count: int,
    ):
        self.pairing = pairing
        self.p1_name = p1_name
        self.p2_name = p2_name
        self.digital_label = digital_label
        self.is_manual = is_manual
        self.is_excluded = is_excluded
        self.has_assignment = has_assignment
        self.p1_count = p1_count
        self.p2_count = p2_count
        self.combined_count = combined_count


class RoundViewPresenter:
    """Presenter for round view: loads round data and prepares display data."""

    def __init__(self, session: Session, tournament_id: int):
        self.session = session
        self.tournament_id = tournament_id

    def get_round_labels(self) -> list[str]:
        """Get list of round labels for the combo box."""
        rounds = get_all_rounds(self.session, self.tournament_id)
        return [f"Round {r.round_number}" for r in rounds]

    def get_round_by_label(self, label: str) -> Optional[Round]:
        """Get a Round object by its combo box label."""
        if not label:
            return None
        round_num = int(label.replace("Round ", ""))
        return get_round(self.session, self.tournament_id, round_num)

    def get_participant_rows(self) -> list[ParticipantRow]:
        """Get sorted participant data for the participants table."""
        participants = get_all_participants(self.session, self.tournament_id)
        rows = []

        for p in participants:
            digital_count = count_digital_rounds_for_participant(
                self.session, p.id
            )
            rows.append(
                ParticipantRow(rank=0, name=p.name, digital_count=digital_count)
            )

        # Sort by digital count descending, then name ascending
        rows.sort(key=lambda r: (-r.digital_count, r.name))

        # Assign ranks
        for i, row in enumerate(rows):
            row.rank = i + 1

        return rows

    def get_pairing_cards(self, round_obj: Round) -> list[PairingCardData]:
        """Get pairing card data for a round."""
        pairings = get_round_pairings(self.session, round_obj.id)
        cards = []

        for pairing in pairings:
            assignment = get_digital_assignment(self.session, pairing.id)

            p1_count = count_digital_rounds_for_participant(
                self.session, pairing.participant1_id
            )
            p2_count = count_digital_rounds_for_participant(
                self.session, pairing.participant2_id
            )

            cards.append(
                PairingCardData(
                    pairing=pairing,
                    p1_name=pairing.participant1.name,
                    p2_name=pairing.participant2.name,
                    digital_label=(
                        assignment.digital_board_label if assignment else None
                    ),
                    is_manual=assignment.is_manual if assignment else False,
                    is_excluded=assignment.is_excluded if assignment else False,
                    has_assignment=assignment is not None,
                    p1_count=p1_count,
                    p2_count=p2_count,
                    combined_count=p1_count + p2_count,
                )
            )

        return cards
