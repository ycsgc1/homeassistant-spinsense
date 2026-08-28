"""The one piece of logic in this integration that can be tested without a
Home Assistant environment. play_clock.py deliberately imports nothing from HA
so that stays true."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components", "spinsense"))

import play_clock  # noqa: E402

class T(unittest.TestCase):
    def test_needle_drop_at_the_top(self):
        # The ordinary case: caught the track ~1s in.
        self.assertEqual(
            play_clock.parse({"play_clock": {"started_at": 1000, "join_offset_secs": 1,
                                             "duration_secs": 220}}),
            (220, 1, 1001))

    def test_mid_song_join_anchors_where_we_actually_were(self):
        # Needle dropped 184s into a 220s track: HA must show 3:04, not 0:00.
        self.assertEqual(
            play_clock.parse({"play_clock": {"started_at": 816, "join_offset_secs": 184,
                                             "duration_secs": 220}}),
            (220, 184, 1000))

    def test_no_play_clock_means_no_bar(self):
        for p in ({}, {"play_clock": None}, {"play_clock": "nope"}, None, "x"):
            self.assertEqual(play_clock.parse(p), (None, None, None), p)

    def test_unknown_duration_means_no_bar(self):
        for d in (None, 0, "long"):
            self.assertEqual(
                play_clock.parse({"play_clock": {"started_at": 1000, "duration_secs": d}}),
                (None, None, None), d)

    def test_missing_started_at_means_no_bar(self):
        self.assertEqual(
            play_clock.parse({"play_clock": {"duration_secs": 220}}), (None, None, None))

    def test_missing_join_offset_assumes_the_top(self):
        self.assertEqual(
            play_clock.parse({"play_clock": {"started_at": 1000, "duration_secs": 220}}),
            (220, 0, 1000))

    def test_position_is_clamped_into_the_track(self):
        self.assertEqual(play_clock.parse(
            {"play_clock": {"started_at": 1000, "join_offset_secs": 999,
                            "duration_secs": 220}})[1], 220)
        self.assertEqual(play_clock.parse(
            {"play_clock": {"started_at": 1000, "join_offset_secs": -5,
                            "duration_secs": 220}})[1], 0)

    def test_booleans_are_not_numbers(self):
        # `true` would otherwise smuggle itself in as 1.
        self.assertEqual(
            play_clock.parse({"play_clock": {"started_at": 1000, "duration_secs": True}}),
            (None, None, None))

    def test_anchor_reconstructs_the_capture_instant(self):
        # position + updated_at must always describe the same moment.
        duration, position, valid_at = play_clock.parse(
            {"play_clock": {"started_at": 500, "join_offset_secs": 42, "duration_secs": 213}})
        self.assertEqual(valid_at - position, 500)   # back to the track start

if __name__ == "__main__":
    unittest.main(verbosity=1)
