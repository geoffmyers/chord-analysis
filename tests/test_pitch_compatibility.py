"""Tests for pitch-based compatibility scoring."""

import pytest

from chord_analyzer.pitch_compatibility import (
    align_notes_to_beats,
    group_notes_by_beat,
    score_beat,
    score_sample_against_progression,
    _generate_score_reasons,
)
from chord_analyzer.models import (
    NoteEvent,
    UserChordSpec,
    UserProgression,
    PitchAnalysisResult,
)


def create_test_note(
    start: float,
    end: float,
    pitch_class: int,
    confidence: float = 1.0,
    amplitude: float = 1.0,
) -> NoteEvent:
    """Helper to create test NoteEvent objects."""
    midi = 60 + pitch_class  # C4 + pitch_class
    return NoteEvent(
        start_time=start,
        end_time=end,
        pitch_hz=440.0,  # Placeholder
        midi_note=midi,
        pitch_class=pitch_class,
        note_name=f"Note{pitch_class}",
        confidence=confidence,
        amplitude=amplitude,
    )


class TestAlignNotesToBeats:
    """Tests for beat alignment."""

    def test_basic_alignment(self):
        """Test basic note-to-beat alignment."""
        notes = [
            create_test_note(0.0, 0.5, pitch_class=0),  # Beat 1
            create_test_note(0.5, 1.0, pitch_class=4),  # Beat 2
            create_test_note(1.0, 1.5, pitch_class=7),  # Beat 3
        ]
        aligned = align_notes_to_beats(notes, bpm=120, time_signature=(4, 4))

        assert aligned[0].bar == 1
        assert aligned[0].beat == 1.0
        assert aligned[1].bar == 1
        assert aligned[1].beat == 2.0
        assert aligned[2].bar == 1
        assert aligned[2].beat == 3.0

    def test_alignment_across_bars(self):
        """Test alignment across bar boundaries."""
        # At 120 BPM, one beat = 0.5 seconds, one bar = 2 seconds
        notes = [
            create_test_note(0.0, 0.5, pitch_class=0),   # Bar 1, Beat 1
            create_test_note(2.0, 2.5, pitch_class=4),   # Bar 2, Beat 1
            create_test_note(4.0, 4.5, pitch_class=7),   # Bar 3, Beat 1
        ]
        aligned = align_notes_to_beats(notes, bpm=120, time_signature=(4, 4))

        assert aligned[0].bar == 1
        assert aligned[1].bar == 2
        assert aligned[2].bar == 3

    def test_alignment_empty_notes(self):
        """Test alignment with empty note list."""
        aligned = align_notes_to_beats([], bpm=120)
        assert aligned == []


class TestScoreBeat:
    """Tests for per-beat scoring."""

    def test_perfect_chord_tone_score(self):
        """Test scoring when all notes are chord tones."""
        # C major chord tones: C(0), E(4), G(7)
        notes = [
            create_test_note(0.0, 0.5, pitch_class=0),  # C
            create_test_note(0.0, 0.5, pitch_class=4),  # E
            create_test_note(0.0, 0.5, pitch_class=7),  # G
        ]
        chord = UserChordSpec(root="C", quality="maj", duration_beats=4)

        score, in_chord, in_scale, clashes = score_beat(notes, chord)

        assert in_chord == 1.0  # All notes are chord tones
        assert in_scale == 1.0  # All chord tones are also in scale
        assert clashes == 0
        assert score >= 80  # High score for perfect chord tones

    def test_scale_tone_only_score(self):
        """Test scoring when notes are in scale but not chord tones."""
        # C major scale tones that aren't chord tones: D(2), F(5), A(9), B(11)
        notes = [
            create_test_note(0.0, 0.5, pitch_class=2),  # D
            create_test_note(0.0, 0.5, pitch_class=5),  # F
        ]
        chord = UserChordSpec(root="C", quality="maj", duration_beats=4)

        score, in_chord, in_scale, clashes = score_beat(notes, chord)

        assert in_chord == 0.0  # No chord tones
        assert in_scale == 1.0  # All in scale
        assert score < 80 and score > 40  # Moderate score

    def test_chromatic_note_score(self):
        """Test scoring with chromatic (out of scale) notes."""
        # C# (1) is chromatic to C major
        notes = [
            create_test_note(0.0, 0.5, pitch_class=1),  # C#
        ]
        chord = UserChordSpec(root="C", quality="maj", duration_beats=4)

        score, in_chord, in_scale, clashes = score_beat(notes, chord)

        assert in_chord == 0.0
        assert in_scale == 0.0  # C# not in C major scale
        assert clashes > 0  # C# clashes with C (semitone)

    def test_chromatic_note_clash_wraps_at_octave_boundary(self):
        """B (11) is a semitone below C (0): the clash must be detected even
        though pitch classes wrap around at the octave boundary rather than
        being adjacent on a simple number line (11 and 0 differ by 11, not 1,
        under a naive `abs(pc - tone) % 12` check)."""
        notes = [
            create_test_note(0.0, 0.5, pitch_class=11),  # B
        ]
        chord = UserChordSpec(root="C", quality="maj", duration_beats=4)

        score, in_chord, in_scale, clashes = score_beat(notes, chord)

        assert in_chord == 0.0
        assert clashes > 0  # B clashes with C (semitone, wrapping B->C)

    def test_empty_beat_score(self):
        """Test scoring for empty beat returns neutral score."""
        chord = UserChordSpec(root="C", quality="maj", duration_beats=4)
        score, in_chord, in_scale, clashes = score_beat([], chord)

        assert score == 50.0  # Neutral score for empty beat
        assert clashes == 0


class TestScoreSampleAgainstProgression:
    """Tests for full sample scoring."""

    def test_basic_scoring(self):
        """Test basic sample scoring."""
        # Create a simple progression: C major for 4 beats
        progression = UserProgression(
            chords=[UserChordSpec(root="C", quality="maj", duration_beats=4)],
            bpm=120,
        )

        # Create pitch analysis with C major chord tones
        pitch_analysis = PitchAnalysisResult(
            filepath="/test/sample.wav",
            notes=[
                create_test_note(0.0, 0.5, pitch_class=0),  # C on beat 1
                create_test_note(0.5, 1.0, pitch_class=4),  # E on beat 2
                create_test_note(1.0, 1.5, pitch_class=7),  # G on beat 3
            ],
            duration_seconds=2.0,
            is_monophonic=True,
            polyphony_level=1,
        )

        result = score_sample_against_progression(pitch_analysis, progression)

        assert result.overall_score > 60  # Good score for chord tones
        assert result.avg_in_chord_ratio > 0.5
        assert len(result.beat_scores) == 4

    def test_scoring_with_progression_changes(self):
        """Test scoring across chord changes."""
        # Progression: C major (4 beats) -> A minor (4 beats)
        progression = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj", duration_beats=4),
                UserChordSpec(root="A", quality="min", duration_beats=4),
            ],
            bpm=120,
        )

        # Notes that fit both chords (C and E are in both C major and A minor)
        pitch_analysis = PitchAnalysisResult(
            filepath="/test/sample.wav",
            notes=[
                create_test_note(0.0, 0.5, pitch_class=0),  # C - fits C major
                create_test_note(2.0, 2.5, pitch_class=9),  # A - fits A minor
            ],
            duration_seconds=4.0,
            is_monophonic=True,
            polyphony_level=1,
        )

        result = score_sample_against_progression(pitch_analysis, progression)

        assert len(result.beat_scores) == 8  # 8 total beats
        assert result.overall_score > 0  # Has some compatibility


class TestGenerateScoreReasons:
    """Tests for score reason generation."""

    def test_excellent_score_reasons(self):
        """Test reasons for excellent scores."""
        reasons = _generate_score_reasons(
            overall_score=85,
            avg_in_chord=0.8,
            avg_in_scale=0.95,
            total_clashes=0,
            scored_beats=8,
        )
        assert any("excellent" in r.lower() for r in reasons)
        assert any("no" in r.lower() and "clash" in r.lower() for r in reasons)

    def test_poor_score_reasons(self):
        """Test reasons for poor scores."""
        reasons = _generate_score_reasons(
            overall_score=25,
            avg_in_chord=0.1,
            avg_in_scale=0.4,
            total_clashes=10,
            scored_beats=8,
        )
        assert any("limited" in r.lower() for r in reasons)
        assert any("dissonance" in r.lower() for r in reasons)


class TestNoteEvent:
    """Tests for NoteEvent model."""

    def test_duration_property(self):
        """Test duration calculation."""
        note = create_test_note(1.0, 2.5, pitch_class=0)
        assert note.duration == 1.5

    def test_has_beat_info_false(self):
        """Test has_beat_info when no beat info."""
        note = create_test_note(0.0, 0.5, pitch_class=0)
        assert note.has_beat_info is False

    def test_has_beat_info_true(self):
        """Test has_beat_info when beat info present."""
        note = create_test_note(0.0, 0.5, pitch_class=0)
        note_with_beat = note.with_beat_info(bar=1, beat=1.0)
        assert note_with_beat.has_beat_info is True
        assert note_with_beat.bar == 1
        assert note_with_beat.beat == 1.0

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        note = NoteEvent(
            start_time=0.5,
            end_time=1.5,
            pitch_hz=440.0,
            midi_note=69,
            pitch_class=9,
            note_name="A4",
            confidence=0.9,
            amplitude=0.8,
            bar=2,
            beat=3.0,
        )
        data = note.to_dict()
        restored = NoteEvent.from_dict(data)

        assert restored.start_time == note.start_time
        assert restored.pitch_class == note.pitch_class
        assert restored.bar == note.bar


class TestUserChordSpec:
    """Tests for UserChordSpec model."""

    def test_chord_label(self):
        """Test chord label generation."""
        chord = UserChordSpec(root="C", quality="maj7", duration_beats=4)
        assert chord.chord_label == "C:maj7"

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        chord = UserChordSpec(root="Bb", quality="min7", duration_beats=2.5)
        data = chord.to_dict()
        restored = UserChordSpec.from_dict(data)

        assert restored.root == chord.root
        assert restored.quality == chord.quality
        assert restored.duration_beats == chord.duration_beats
