"""Manual entry presenter - handles manual round entry logic."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from database.queries import get_all_participants, get_max_round, get_tournament
from logic.pairing import PairingData, RoundData
from logic.tournament import import_rounds_from_data


class ManualEntryPresenter:
    """Handles manual round entry logic.

    Separates manual entry orchestration from GUI concerns.
    """

    def __init__(
        self,
        session: Session,
        tournament_id: int,
        on_round_added: Callable[[int, int], None],
    ):
        self.session = session
        self.tournament_id = tournament_id
        self.on_round_added = on_round_added

    def get_next_round_number(self) -> int:
        """Calculate the next round number based on existing rounds."""
        max_round = get_max_round(self.session, self.tournament_id)
        return max_round + 1 if max_round else 1

    def get_participant_names(self) -> list[str]:
        """Get sorted list of existing participant names."""
        participants = get_all_participants(self.session, self.tournament_id)
        return [p.name for p in participants]

    def import_manual_round(self, round_num: int, pairings_dict: list[dict]) -> None:
        """Import a manually entered round into the database."""
        pairings = self._create_pairing_data(pairings_dict)
        round_data = RoundData(round_number=round_num, pairings=pairings)
        tournament = get_tournament(self.session, self.tournament_id)
        tournament_type = tournament.tournament_type if tournament else "individual"

        import_rounds_from_data(
            self.session, self.tournament_id, [round_data], tournament_type
        )

        self.on_round_added(round_num, len(pairings))

    def _create_pairing_data(self, pairings_dict: list[dict]) -> list[PairingData]:
        """Create PairingData objects from manual entry."""
        return [
            PairingData(
                participant1_name=p["participant1"],
                participant2_name=p["participant2"],
                board_number=p.get("board_number"),
            )
            for p in pairings_dict
        ]
