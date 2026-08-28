"""Turning SpinSense's `play_clock` frame block into Home Assistant's
media-position model.

Deliberately free of Home Assistant imports so the arithmetic can be tested
without a HA environment; `media_player.py` converts the timestamp to an aware
datetime at the edge.

**Why an anchor rather than a running position.** Home Assistant does not want a
stream of positions. You give it a position plus the instant that position was
true, and the frontend extrapolates the progress bar itself. SpinSense's engine
pushes a frame roughly once a second, so recomputing "seconds elapsed" on every
frame would change an attribute every second — a state_changed event and a
recorder row per second, per turntable, forever.

Instead both values are pinned to the moment of the recognition capture and stay
constant for the whole track: `position` is where the playhead was, `updated_at`
is when it was there. The bar is exact at every instant, drifts by nothing, and
survives WebSocket gaps and Home Assistant restarts, while the state machine
sees an attribute change only when the track does.
"""


def _as_int(value):
    """Ints from a network payload, or None. Bools are not integers here — a
    stray `true` becoming position 1 would be worse than no position at all."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def parse(payload) -> tuple[int | None, int | None, int | None]:
    """(duration_secs, position_secs, position_valid_at_unix) from a live frame.

    All-None whenever a progress bar would be a guess rather than a fact:

    - no `play_clock` at all — an older SpinSense engine, which simply never
      sends one;
    - no `duration_secs` — the track length was never resolved (Shazam alone
      supplies none, and the iTunes lookup can miss), and a progress bar with no
      end is not a progress bar;
    - no `started_at` — nothing to anchor to.

    `join_offset_secs` missing is not fatal: it means we believe we caught the
    track from the top, which is the ordinary needle-drop case.
    """
    if not isinstance(payload, dict):
        return None, None, None
    clock = payload.get("play_clock")
    if not isinstance(clock, dict):
        return None, None, None

    duration = _as_int(clock.get("duration_secs"))
    started_at = _as_int(clock.get("started_at"))
    if not duration or duration <= 0 or started_at is None:
        return None, None, None

    position = _as_int(clock.get("join_offset_secs")) or 0
    position = max(0, min(position, duration))

    # started_at is when the track began; the playhead was `position` one
    # `position` later — the instant the capture started. That pair is what HA
    # extrapolates from, and neither half moves again until the track changes.
    return duration, position, started_at + position
