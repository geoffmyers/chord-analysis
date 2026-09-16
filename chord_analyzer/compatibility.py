"""
Compatibility scoring engine for finding harmonically compatible samples.
"""

from collections import Counter
from typing import List, Dict, Any, Set, Optional, Tuple

from .models import ChordEvent
from .theory import (
    parse_chord_label,
    get_chord_notes,
    get_all_notes_in_progression,
    NOTE_TO_SEMITONE,
    is_transposition,
    get_transposition_interval,
    calculate_functional_similarity,
    normalize_progression,
    SEMITONE_TO_NOTE,
)


def calculate_compatibility(prog_a: List[str], prog_b: List[str]) -> Dict[str, Any]:
    """
    Calculate harmonic compatibility score between two chord progressions.

    Uses both absolute (key-specific) and relative (key-agnostic) factors:

    Absolute factors:
    - Shared chords (20 points max): Exact chord matches
    - Note overlap (15 points max): Common notes suggest compatible scales
    - Harmonic relations (15 points max): Circle of fifths relationships
    - Clash penalty (-15 points max): Semitone conflicts

    Relative/functional factors:
    - Functional match (35 points max): Key-agnostic pattern matching
      (detects transpositions, similar interval patterns, Roman numeral similarity)
    - Mood match (15 points max): Major/minor balance similarity

    Args:
        prog_a: First chord progression (list of chord labels)
        prog_b: Second chord progression (list of chord labels)

    Returns:
        Dictionary with:
        - overall: Total score (0-100)
        - components: Individual score components
        - reasons: Human-readable explanations
        - is_transposition: True if progressions are exact transpositions
        - transposition_interval: Semitones to transpose (if applicable)
    """
    # Filter out None values and empty strings
    prog_a = [c for c in prog_a if c]
    prog_b = [c for c in prog_b if c]

    if not prog_a or not prog_b:
        return {"overall": 0, "components": {}, "reasons": ["Empty progression"]}

    scores: Dict[str, float] = {}
    reasons: List[str] = []

    # Check for transposition first (this is the most important match)
    transposition = is_transposition(prog_a, prog_b)
    transposition_interval = None

    if transposition:
        transposition_interval = get_transposition_interval(prog_a, prog_b)

    # 1. Functional match score (key-agnostic) - HIGHEST WEIGHT
    functional_score, functional_reasons = _score_functional_match(
        prog_a, prog_b, transposition, transposition_interval
    )
    scores["functional_match"] = functional_score
    reasons.extend(functional_reasons)

    # 2. Shared chords score (exact matches)
    shared_score, shared_reasons = _score_shared_chords(prog_a, prog_b)
    scores["shared_chords"] = shared_score
    reasons.extend(shared_reasons)

    # 3. Note overlap score
    notes_a = get_all_notes_in_progression(prog_a)
    notes_b = get_all_notes_in_progression(prog_b)

    overlap_score, clash_penalty, note_reasons = _score_note_overlap(notes_a, notes_b)
    scores["note_overlap"] = overlap_score
    scores["clash_penalty"] = clash_penalty
    reasons.extend(note_reasons)

    # 4. Harmonic relations score (circle of fifths)
    harmonic_score, harmonic_reasons = _score_harmonic_relations(prog_a, prog_b)
    scores["harmonic_relations"] = harmonic_score
    reasons.extend(harmonic_reasons)

    # 5. Mood match score (major/minor balance)
    mood_score, mood_reasons = _score_mood_match(prog_a, prog_b)
    scores["mood_match"] = mood_score
    reasons.extend(mood_reasons)

    # Calculate overall score (clamped to 0-100)
    overall = max(0, min(100, sum(scores.values())))

    result = {
        "overall": round(overall, 1),
        "components": scores,
        "reasons": reasons,
        "is_transposition": transposition,
    }

    if transposition_interval is not None:
        result["transposition_interval"] = transposition_interval
        result["transposition_note"] = SEMITONE_TO_NOTE.get(transposition_interval, "?")

    return result


def _score_functional_match(
    prog_a: List[str],
    prog_b: List[str],
    is_exact_transposition: bool,
    transposition_interval: int | None,
) -> tuple[float, List[str]]:
    """
    Score based on functional/relative similarity (key-agnostic).

    This is the most important factor for finding samples that can be
    transposed to work together.

    Max score: 35 points
    """
    reasons = []

    # Exact transposition = maximum score
    if is_exact_transposition:
        if transposition_interval == 0:
            reasons.append("Identical progression")
        else:
            interval_name = _interval_to_name(transposition_interval)
            reasons.append(f"Exact transposition ({interval_name})")
        return 35.0, reasons

    # Calculate functional similarity for non-exact matches
    similarity = calculate_functional_similarity(prog_a, prog_b)
    score = similarity * 35  # Max 35 points

    if similarity >= 0.7:
        reasons.append("Similar functional progression (easily transposable)")
    elif similarity >= 0.4:
        reasons.append("Partially similar chord movement patterns")

    return score, reasons


def _interval_to_name(semitones: int) -> str:
    """Convert semitone interval to human-readable name."""
    names = {
        0: "unison",
        1: "minor 2nd",
        2: "major 2nd",
        3: "minor 3rd",
        4: "major 3rd",
        5: "perfect 4th",
        6: "tritone",
        7: "perfect 5th",
        8: "minor 6th",
        9: "major 6th",
        10: "minor 7th",
        11: "major 7th",
    }
    return names.get(semitones % 12, f"{semitones} semitones")


def _score_shared_chords(
    prog_a: List[str], prog_b: List[str]
) -> tuple[float, List[str]]:
    """
    Score based on exact chord matches between progressions.

    Max score: 20 points
    """
    set_a = set(prog_a)
    set_b = set(prog_b)
    shared = set_a & set_b

    if not set_a or not set_b:
        return 0.0, []

    # Ratio of shared chords to the larger set
    ratio = len(shared) / max(len(set_a), len(set_b))
    score = ratio * 20  # Max 20 points

    reasons = []
    if shared:
        shared_list = sorted(shared)[:5]  # Show max 5 chords
        if len(shared) > 5:
            reasons.append(f"Shared chords: {', '.join(shared_list)} (+{len(shared) - 5} more)")
        else:
            reasons.append(f"Shared chords: {', '.join(shared_list)}")

    return score, reasons


def _score_note_overlap(
    notes_a: Set[int], notes_b: Set[int]
) -> tuple[float, float, List[str]]:
    """
    Score based on shared notes and detect semitone clashes.

    Note overlap max: 15 points
    Clash penalty max: -15 points
    """
    if not notes_a or not notes_b:
        return 0.0, 0.0, []

    # Calculate overlap ratio (Jaccard similarity)
    intersection = notes_a & notes_b
    union = notes_a | notes_b
    overlap_ratio = len(intersection) / len(union)
    overlap_score = overlap_ratio * 15  # Max 15 points

    # Detect semitone clashes (notes that are 1 semitone apart)
    clash_count = 0
    for note in notes_a:
        if (note + 1) % 12 in notes_b:
            clash_count += 1
        if (note - 1) % 12 in notes_b:
            clash_count += 1

    # Divide by 2 to avoid double-counting
    clash_count = clash_count // 2
    clash_penalty = -min(clash_count * 5, 15)  # Max -15 points

    reasons = []
    if clash_count > 0:
        reasons.append(f"Potential clashes: {clash_count} semitone conflicts")

    return overlap_score, clash_penalty, reasons


def _score_harmonic_relations(
    prog_a: List[str], prog_b: List[str]
) -> tuple[float, List[str]]:
    """
    Score based on circle of fifths relationships between root notes.

    Strong relationships (unison, P4, P5): 2 points each
    Medium relationships (3rds, 6ths): 1 point each

    Max score: 15 points
    """
    # Extract root notes
    roots_a = [parse_chord_label(c)[0] for c in prog_a]
    roots_b = [parse_chord_label(c)[0] for c in prog_b]

    # Convert to semitones
    semitones_a = set(
        NOTE_TO_SEMITONE[r] for r in roots_a if r in NOTE_TO_SEMITONE
    )
    semitones_b = set(
        NOTE_TO_SEMITONE[r] for r in roots_b if r in NOTE_TO_SEMITONE
    )

    if not semitones_a or not semitones_b:
        return 0.0, []

    strong_relations = 0
    medium_relations = 0

    for sa in semitones_a:
        for sb in semitones_b:
            interval = abs(sa - sb) % 12

            # Strong harmonic relationships
            if interval in [0, 5, 7]:  # Unison, Perfect 4th, Perfect 5th
                strong_relations += 1
            # Medium relationships
            elif interval in [3, 4, 8, 9]:  # Minor 3rd, Major 3rd, Minor 6th, Major 6th
                medium_relations += 1

    total_points = (strong_relations * 2) + medium_relations
    score = min(total_points * 2, 15)  # Max 15 points

    reasons = []
    if strong_relations > 0:
        reasons.append(f"Strong harmonic relations: {strong_relations} (P4/P5/unison)")

    return score, reasons


def _score_mood_match(
    prog_a: List[str], prog_b: List[str]
) -> tuple[float, List[str]]:
    """
    Score based on similar major/minor balance between progressions.

    Max score: 15 points
    """
    # Count chord types
    types_a = Counter(parse_chord_label(c)[1] for c in prog_a)
    types_b = Counter(parse_chord_label(c)[1] for c in prog_b)

    # Count major vs minor chords
    major_types = {"maj", "maj7", "6", "add9", "maj9"}
    minor_types = {"min", "min7", "min6", "min9", "dim", "dim7", "hdim7"}

    major_a = sum(types_a.get(t, 0) for t in major_types)
    minor_a = sum(types_a.get(t, 0) for t in minor_types)
    major_b = sum(types_b.get(t, 0) for t in major_types)
    minor_b = sum(types_b.get(t, 0) for t in minor_types)

    total_a = major_a + minor_a
    total_b = major_b + minor_b

    if total_a == 0 or total_b == 0:
        return 0.0, []

    # Calculate major/minor ratios
    ratio_a = major_a / total_a
    ratio_b = major_b / total_b

    # Similarity score (1 = identical balance, 0 = opposite)
    similarity = 1 - abs(ratio_a - ratio_b)
    score = similarity * 15  # Max 15 points

    reasons = []
    if similarity > 0.7:
        if ratio_a > 0.5 and ratio_b > 0.5:
            reasons.append("Similar major tonality")
        elif ratio_a <= 0.5 and ratio_b <= 0.5:
            reasons.append("Similar minor tonality")
        else:
            reasons.append("Compatible mood balance")

    return score, reasons


def explain_compatibility(
    prog_a: List[str], prog_b: List[str], verbose: bool = False
) -> str:
    """
    Generate a human-readable explanation of compatibility between progressions.

    Args:
        prog_a: First progression
        prog_b: Second progression
        verbose: Include detailed score breakdown

    Returns:
        Formatted explanation string
    """
    result = calculate_compatibility(prog_a, prog_b)

    lines = [
        f"Overall Compatibility Score: {result['overall']}/100",
        "",
    ]

    if result["reasons"]:
        lines.append("Key Factors:")
        for reason in result["reasons"]:
            lines.append(f"  - {reason}")
        lines.append("")

    if verbose and result["components"]:
        lines.append("Score Breakdown:")
        for component, value in result["components"].items():
            name = component.replace("_", " ").title()
            lines.append(f"  {name}: {value:+.1f}")

    return "\n".join(lines)


def rank_samples_by_compatibility(
    target_progression: List[str],
    candidate_progressions: List[tuple[str, List[str]]],
    min_score: float = 0.0,
) -> List[tuple[str, float, Dict[str, Any]]]:
    """
    Rank a list of candidate samples by compatibility with a target.

    Args:
        target_progression: The reference progression to compare against
        candidate_progressions: List of (identifier, progression) tuples
        min_score: Minimum score threshold

    Returns:
        List of (identifier, score, details) tuples, sorted by score descending
    """
    results = []

    for identifier, progression in candidate_progressions:
        compat = calculate_compatibility(target_progression, progression)
        if compat["overall"] >= min_score:
            results.append((identifier, compat["overall"], compat))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)

    return results


def _score_tempo_compatibility(
    bpm_a: float,
    bpm_b: float,
    max_score: float = 10.0,
) -> Tuple[float, List[str]]:
    """
    Score tempo compatibility between two samples.

    Samples can work together if they:
    - Have identical or very similar BPM
    - Are in half-time or double-time relationships (2:1 or 1:2 ratio)
    - Have close enough tempos to be adjusted without artifacts

    Args:
        bpm_a: BPM of first sample
        bpm_b: BPM of second sample
        max_score: Maximum points for perfect tempo match

    Returns:
        Tuple of (score, list of reasons)
    """
    reasons = []

    if bpm_a <= 0 or bpm_b <= 0:
        return 0.0, []

    # Calculate tempo ratio (always >= 1)
    ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)

    # Perfect match (within 1%)
    if 0.99 <= ratio <= 1.01:
        reasons.append(f"Perfect tempo match ({bpm_a:.0f} BPM)")
        return max_score, reasons

    # Double-time or half-time relationship (within 2%)
    if 1.96 <= ratio <= 2.04:
        slower_bpm = min(bpm_a, bpm_b)
        faster_bpm = max(bpm_a, bpm_b)
        reasons.append(f"Double-time relationship ({slower_bpm:.0f} / {faster_bpm:.0f} BPM)")
        return max_score * 0.9, reasons

    # Very close tempo (within 5%)
    if 0.95 <= ratio <= 1.05:
        reasons.append(f"Very similar tempo ({bpm_a:.0f} / {bpm_b:.0f} BPM)")
        return max_score * 0.85, reasons

    # Close tempo (within 10%)
    if 0.90 <= ratio <= 1.10:
        reasons.append(f"Close tempo ({bpm_a:.0f} / {bpm_b:.0f} BPM)")
        return max_score * 0.6, reasons

    # Moderately different tempo (10-25% difference)
    if 0.75 <= ratio <= 1.25:
        reasons.append(f"Moderately different tempo ({bpm_a:.0f} / {bpm_b:.0f} BPM)")
        return max_score * 0.3, reasons

    # Very different tempo
    reasons.append(f"Very different tempo ({bpm_a:.0f} / {bpm_b:.0f} BPM)")
    return max_score * 0.1, reasons


def calculate_rhythm_similarity(
    chords_a: List[ChordEvent],
    chords_b: List[ChordEvent],
) -> Tuple[float, List[str]]:
    """
    Calculate rhythmic similarity between two chord sequences.

    This compares the relative timing of chord changes, independent of
    absolute tempo. Two samples with the same chord pattern occurring
    on the same beats will score highly even at different BPMs.

    Args:
        chords_a: First chord sequence with beat info
        chords_b: Second chord sequence with beat info

    Returns:
        Tuple of (similarity score 0-1, list of reasons)
    """
    reasons = []

    # Check if both have beat information
    has_beat_a = all(c.has_beat_info for c in chords_a) if chords_a else False
    has_beat_b = all(c.has_beat_info for c in chords_b) if chords_b else False

    if not has_beat_a or not has_beat_b:
        return 0.0, ["Beat information not available for rhythm comparison"]

    if not chords_a or not chords_b:
        return 0.0, []

    # Normalize chord positions to relative positions (0-1 scale)
    def normalize_positions(chords: List[ChordEvent]) -> List[Tuple[float, str]]:
        if not chords:
            return []

        # Calculate total length in beats
        first_bar = chords[0].bar
        first_beat = chords[0].beat
        last = chords[-1]

        bar_span = last.bar - first_bar
        beat_span = (last.beat - first_beat) + (last.duration_beats or 1.0)
        total_beats = bar_span * 4 + beat_span  # Assuming 4/4

        if total_beats <= 0:
            return []

        # Normalize each chord position
        result = []
        for chord in chords:
            bar_offset = chord.bar - first_bar
            beat_offset = chord.beat - first_beat
            absolute_beat = bar_offset * 4 + beat_offset
            normalized_pos = absolute_beat / total_beats
            result.append((normalized_pos, chord.chord_label))

        return result

    norm_a = normalize_positions(chords_a)
    norm_b = normalize_positions(chords_b)

    if not norm_a or not norm_b:
        return 0.0, []

    # Compare rhythm patterns
    # Method 1: Check if chord changes happen at similar relative positions
    position_matches = 0
    total_positions = max(len(norm_a), len(norm_b))

    # Build position sets (with tolerance)
    tolerance = 0.1  # 10% tolerance for position matching
    positions_a = {pos for pos, _ in norm_a}
    positions_b = {pos for pos, _ in norm_b}

    for pos_a in positions_a:
        for pos_b in positions_b:
            if abs(pos_a - pos_b) < tolerance:
                position_matches += 1
                break

    position_similarity = position_matches / total_positions if total_positions > 0 else 0

    # Method 2: Check beat alignment (chords on same beat numbers)
    beat_positions_a = {(c.bar % 4, round(c.beat)) for c in chords_a if c.bar and c.beat}
    beat_positions_b = {(c.bar % 4, round(c.beat)) for c in chords_b if c.bar and c.beat}

    common_beats = beat_positions_a & beat_positions_b
    total_beats = len(beat_positions_a | beat_positions_b)
    beat_alignment = len(common_beats) / total_beats if total_beats > 0 else 0

    # Combine methods (weighted average)
    similarity = (position_similarity * 0.6) + (beat_alignment * 0.4)

    if similarity > 0.7:
        reasons.append("Similar rhythm patterns (chord changes on same beats)")
    elif similarity > 0.4:
        reasons.append("Partially aligned rhythm patterns")

    return similarity, reasons


def calculate_compatibility_with_rhythm(
    chords_a: List[ChordEvent],
    chords_b: List[ChordEvent],
    rhythm_weight: float = 15.0,
    bpm_a: Optional[float] = None,
    bpm_b: Optional[float] = None,
    tempo_weight: float = 10.0,
) -> Dict[str, Any]:
    """
    Calculate compatibility with rhythm pattern and tempo consideration.

    This is an enhanced version of calculate_compatibility that also
    considers when chord changes occur relative to beats and tempo compatibility.

    Args:
        chords_a: First chord sequence (with optional beat info)
        chords_b: Second chord sequence (with optional beat info)
        rhythm_weight: Maximum points for rhythm similarity (default 15)
        bpm_a: BPM of first sample (optional)
        bpm_b: BPM of second sample (optional)
        tempo_weight: Maximum points for tempo compatibility (default 10)

    Returns:
        Dictionary with overall score, components, and reasons
    """
    # Extract progressions for harmonic comparison
    prog_a = [c.chord_label for c in chords_a]
    prog_b = [c.chord_label for c in chords_b]

    # Get base harmonic compatibility
    result = calculate_compatibility(prog_a, prog_b)

    # Add rhythm similarity if beat info is available
    rhythm_score, rhythm_reasons = calculate_rhythm_similarity(chords_a, chords_b)

    if rhythm_score > 0:
        weighted_rhythm = rhythm_score * rhythm_weight
        result["components"]["rhythm_match"] = weighted_rhythm
        result["reasons"].extend(rhythm_reasons)

    # Add tempo compatibility if BPM values are available
    if bpm_a and bpm_b:
        tempo_score, tempo_reasons = _score_tempo_compatibility(bpm_a, bpm_b, tempo_weight)
        result["components"]["tempo_match"] = tempo_score
        result["reasons"].extend(tempo_reasons)

    # Recalculate overall (capped at 100)
    result["overall"] = min(100, round(sum(result["components"].values()), 1))

    return result


def get_chord_beat_pattern(chords: List[ChordEvent]) -> List[Tuple[int, float]]:
    """
    Extract the beat pattern of chord changes.

    Returns a list of (beat_in_bar, duration_beats) tuples representing
    where chord changes occur within each bar.

    Args:
        chords: List of ChordEvent objects with beat info

    Returns:
        List of (beat_position, duration) tuples
    """
    pattern = []

    for chord in chords:
        if chord.has_beat_info:
            # Normalize beat position to within a single bar (1-4 for 4/4)
            beat_pos = chord.beat if chord.beat else 1.0
            duration = chord.duration_beats if chord.duration_beats else 1.0
            pattern.append((beat_pos, duration))

    return pattern


def compare_beat_patterns(
    pattern_a: List[Tuple[int, float]],
    pattern_b: List[Tuple[int, float]],
) -> float:
    """
    Compare two beat patterns for similarity.

    Args:
        pattern_a: First beat pattern
        pattern_b: Second beat pattern

    Returns:
        Similarity score (0-1)
    """
    if not pattern_a or not pattern_b:
        return 0.0

    # Count beat positions used in each pattern
    positions_a = Counter(pos for pos, _ in pattern_a)
    positions_b = Counter(pos for pos, _ in pattern_b)

    # Calculate Jaccard-like similarity
    all_positions = set(positions_a.keys()) | set(positions_b.keys())
    if not all_positions:
        return 0.0

    similarity_sum = 0
    for pos in all_positions:
        count_a = positions_a.get(pos, 0)
        count_b = positions_b.get(pos, 0)
        # Similarity contribution based on min/max ratio
        if count_a > 0 or count_b > 0:
            similarity_sum += min(count_a, count_b) / max(count_a, count_b)

    return similarity_sum / len(all_positions)
