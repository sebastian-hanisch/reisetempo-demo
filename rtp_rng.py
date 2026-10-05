"""SplitMix64 (Vigna) in reiner Ganzzahl-Arithmetik: Zufallszahlen für Höhenprofil und Wind der Strecke.

numpy garantiert keine versionsstabilen Zufallsströme, die CI installiert die neueste Version; SplitMix64 liefert überall dieselbe Zahlenfolge."""

_MASK = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15
_C1 = 0xBF58476D1CE4E5B9
_C2 = 0x94D049BB133111EB


class SplitMix64:
    """Skalarer Generator."""

    def __init__(self, seed):
        self.state = seed & _MASK

    def next(self):
        self.state = (self.state + GAMMA) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * _C1) & _MASK
        z = ((z ^ (z >> 27)) * _C2) & _MASK
        return z ^ (z >> 31)

    def below(self, n):
        """Ganzzahl in 0..n-1."""
        return self.next() % n

    def between(self, lo, hi):
        """Ganzzahl in lo..hi (beide eingeschlossen)."""
        return lo + self.below(hi - lo + 1)
