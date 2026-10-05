"""Sucht einen Seed außerhalb der Messreihen-Seeds, bei dem alle Kriterien aller Presets gelten (rtp_stories.CRITERIA).

    python tools/preset_search.py                 # Seeds 500 bis 600
    python tools/preset_search.py --from 600 --to 700

Meldet je Seed, welche Kriterien welches Presets verletzt sind, und gibt den ersten Seed aus, bei dem keines verletzt ist."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rtp_constants as C  # noqa: E402
import rtp_evaluation as E  # noqa: E402
import rtp_results as R  # noqa: E402
import rtp_stories as S  # noqa: E402


def failing(res: dict, seed: int) -> dict:
    out = {}
    for name in C.PRESET_ORDER:
        settings = {**C.PRESETS[name], "seed": seed}
        run = E.run_live(settings)
        ref = E.run_live(S.ref_settings(name, settings)) if name in S.REF_OVERRIDES else run
        bad = [cid for cid, _, ok in S.check(name, S.facts_for(name, run, ref, res)) if not ok]
        if bad:
            out[name] = bad
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="lo", type=int, default=500)
    ap.add_argument("--to", dest="hi", type=int, default=600)
    args = ap.parse_args()
    res = R.load_results()
    for seed in range(args.lo, args.hi):
        bad = failing(res, seed)
        print(seed, "OK" if not bad else bad, flush=True)
        if not bad:
            print(f"Seed {seed}: alle Kriterien aller Presets erfüllt")
            return
    print("kein Seed gefunden")


if __name__ == "__main__":
    main()
