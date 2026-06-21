from dataclasses import dataclass


@dataclass
class PairingData:
    """Represents a pairing between two participants."""

    participant1_name: str
    participant2_name: str
    board_number: int | None = None
    score1: float | None = None
    score2: float | None = None

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
    source_url: str | None = None
