"""SplitMix64 gegen die veröffentlichten Referenzwerte (Vigna, Seed 0), Zustandsfortschreibung und die Grenzen von below und between."""
import pytest

from rtp_rng import GAMMA, SplitMix64

MASK = (1 << 64) - 1


def test_reference_values_for_seed_zero():
    r = SplitMix64(0)
    assert [r.next() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_the_state_advances_by_gamma_modulo_two_to_the_64():
    r = SplitMix64(5)
    assert r.state == 5
    r.next()
    assert r.state == 5 + GAMMA
    r.next()
    assert r.state == (5 + 2 * GAMMA) & MASK
    big = SplitMix64(MASK)                                   # Überlauf: (2^64 - 1) + GAMMA = GAMMA - 1 modulo 2^64
    big.next()
    assert big.state == GAMMA - 1


def test_the_seed_is_reduced_to_64_bits():
    assert SplitMix64((1 << 64) + 5).state == 5 and SplitMix64(-1).state == MASK


def test_same_seed_same_stream_other_seed_other_stream():
    a, b, c = SplitMix64(42), SplitMix64(42), SplitMix64(43)
    xs, ys, zs = [a.next() for _ in range(10)], [b.next() for _ in range(10)], [c.next() for _ in range(10)]
    assert xs == ys and xs != zs and len(set(xs)) == 10


def test_below_is_the_remainder_of_the_next_output():
    a, b = SplitMix64(7), SplitMix64(7)
    assert [a.below(1000) for _ in range(5)] == [b.next() % 1000 for _ in range(5)]


def test_below_one_is_always_zero_and_stays_below_n():
    r = SplitMix64(1)
    assert all(r.below(1) == 0 for _ in range(20))
    draws = [SplitMix64(s).below(6) for s in range(600)]
    assert set(draws) == set(range(6)) and all(abs(draws.count(i) - 100) < 40 for i in range(6))      # grob gleichverteilt (Erwartung 100, Streuung etwa 9)


def test_between_includes_both_ends_and_equals_lo_plus_below():
    a, b = SplitMix64(9), SplitMix64(9)
    assert [a.between(-3, 4) for _ in range(5)] == [-3 + b.below(8) for _ in range(5)]
    r = SplitMix64(2)
    draws = [r.between(-3, 4) for _ in range(400)]
    assert min(draws) == -3 and max(draws) == 4 and set(draws) == set(range(-3, 5))
    assert all(SplitMix64(s).between(3, 3) == 3 for s in range(10))


@pytest.mark.parametrize("n", [2, 3, 1000])
def test_below_values_lie_in_range(n):
    r = SplitMix64(11)
    assert all(0 <= r.below(n) < n for _ in range(200))
