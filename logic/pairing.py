from dataclasses import dataclass
from typing import Optional


@dataclass
class PairingData:
    """Represents a pairing between two participants."""

    participant1_name: str
    participant2_name: str
    board_number: Optional[int] = None
    score1: Optional[float] = None
    score2: Optional[float] = None

    def __str__(self):
        return f"{self.participant1_name} vs {self.participant2_name}"


@dataclass
class RoundData:
    """Represents a round with its pairings."""

    round_number: int
    pairings: list[PairingData]

    def __str__(self):
        return f"Round {self.round_number}: {len(self.pairings)} pairings"


@dataclass
class TournamentData:
    """Represents tournament metadata."""

    name: str
    tournament_type: str  # 'individual' or 'team'
    source_url: Optional[str] = None
