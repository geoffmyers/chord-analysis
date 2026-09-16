"""
Database operations for storing and querying sample data.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import ChordEvent, Sample, CompatibilityResult, PitchAnalysisResult, NoteEvent
from .compatibility import calculate_compatibility, calculate_compatibility_with_rhythm


def init_database(db_path: str) -> sqlite3.Connection:
    """
    Initialize SQLite database with required schema.

    Args:
        db_path: Path to the database file

    Returns:
        Database connection
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Main samples table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            directory TEXT,
            chords_json TEXT,
            progression_json TEXT,
            root_notes_json TEXT,
            chord_types_json TEXT,
            duration_seconds REAL,
            estimated_key TEXT,
            estimated_bpm REAL,
            time_signature TEXT DEFAULT '4/4',
            first_beat_offset REAL DEFAULT 0.0,
            voicing_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Compatibility cache for performance
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS compatibility_cache (
            sample_a_id INTEGER NOT NULL,
            sample_b_id INTEGER NOT NULL,
            score REAL NOT NULL,
            components_json TEXT,
            reasons_json TEXT,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (sample_a_id, sample_b_id),
            FOREIGN KEY (sample_a_id) REFERENCES samples(id) ON DELETE CASCADE,
            FOREIGN KEY (sample_b_id) REFERENCES samples(id) ON DELETE CASCADE
        )
    """
    )

    # Pitch analysis cache table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pitch_analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,
            notes_json TEXT NOT NULL,
            is_monophonic BOOLEAN,
            polyphony_level INTEGER,
            detected_bpm REAL,
            duration_seconds REAL,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Indexes for performance
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_samples_filepath ON samples(filepath)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_samples_key ON samples(estimated_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_samples_bpm ON samples(estimated_bpm)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_compatibility_score ON compatibility_cache(score DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pitch_cache_filepath ON pitch_analysis_cache(filepath)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pitch_cache_hash ON pitch_analysis_cache(file_hash)"
    )

    conn.commit()
    return conn


def store_sample(conn: sqlite3.Connection, sample: Sample) -> int:
    """
    Store a sample in the database.

    Args:
        conn: Database connection
        sample: Sample object to store

    Returns:
        ID of the inserted/updated sample
    """
    filepath_obj = Path(sample.filepath)

    chords_data = [c.to_dict() for c in sample.chords]

    # Format time signature as string
    time_sig_str = f"{sample.time_signature[0]}/{sample.time_signature[1]}"

    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO samples
        (filepath, filename, directory, chords_json, progression_json,
         root_notes_json, chord_types_json, duration_seconds,
         estimated_key, estimated_bpm, time_signature, first_beat_offset, voicing_type, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        (
            str(sample.filepath),
            sample.filename,
            str(filepath_obj.parent),
            json.dumps(chords_data),
            json.dumps(sample.progression),
            json.dumps(list(sample.root_notes)),
            json.dumps(list(sample.chord_types)),
            sample.duration_seconds,
            sample.estimated_key,
            sample.estimated_bpm,
            time_sig_str,
            sample.first_beat_offset,
            sample.voicing_type,
        ),
    )

    conn.commit()
    return cursor.lastrowid


def get_sample_by_filepath(conn: sqlite3.Connection, filepath: str) -> Optional[Sample]:
    """
    Retrieve a sample by its filepath.

    Args:
        conn: Database connection
        filepath: Path to the sample file

    Returns:
        Sample object or None if not found
    """
    cursor = conn.execute(
        "SELECT * FROM samples WHERE filepath = ?",
        (filepath,),
    )
    row = cursor.fetchone()

    if not row:
        return None

    return _row_to_sample(row)


def get_sample_by_id(conn: sqlite3.Connection, sample_id: int) -> Optional[Sample]:
    """
    Retrieve a sample by its ID.

    Args:
        conn: Database connection
        sample_id: Sample ID

    Returns:
        Sample object or None if not found
    """
    cursor = conn.execute(
        "SELECT * FROM samples WHERE id = ?",
        (sample_id,),
    )
    row = cursor.fetchone()

    if not row:
        return None

    return _row_to_sample(row)


def get_all_samples(conn: sqlite3.Connection) -> List[Sample]:
    """
    Retrieve all samples from the database.

    WARNING: This loads ALL samples into memory. For large datasets, use
    get_samples_paginated() or get_sample_count() + get_samples_page() instead.

    Args:
        conn: Database connection

    Returns:
        List of all Sample objects
    """
    cursor = conn.execute("SELECT * FROM samples ORDER BY filename")
    return [_row_to_sample(row) for row in cursor]


def get_sample_count(conn: sqlite3.Connection, where_clause: str = "", params: tuple = ()) -> int:
    """
    Get total count of samples, optionally with filtering.

    Args:
        conn: Database connection
        where_clause: Optional SQL WHERE clause (without the WHERE keyword)
        params: Parameters for the WHERE clause

    Returns:
        Count of matching samples
    """
    query = "SELECT COUNT(*) FROM samples"
    if where_clause:
        query += f" WHERE {where_clause}"
    cursor = conn.execute(query, params)
    return cursor.fetchone()[0]


def get_samples_page(
    conn: sqlite3.Connection,
    limit: int = 50,
    offset: int = 0,
    order_by: str = "filename",
    where_clause: str = "",
    params: tuple = ()
) -> List[Sample]:
    """
    Retrieve a page of samples with pagination support.

    Args:
        conn: Database connection
        limit: Maximum number of samples to return
        offset: Number of samples to skip
        order_by: Column to order by (default: filename)
        where_clause: Optional SQL WHERE clause (without the WHERE keyword)
        params: Parameters for the WHERE clause

    Returns:
        List of Sample objects for the requested page
    """
    query = f"SELECT * FROM samples"
    if where_clause:
        query += f" WHERE {where_clause}"
    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"

    cursor = conn.execute(query, params + (limit, offset))
    return [_row_to_sample(row) for row in cursor]


def get_samples_metadata_only(
    conn: sqlite3.Connection,
    limit: int = None,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve sample metadata WITHOUT chord data for fast loading.

    This is much faster than loading full samples when you only need
    basic info like filename, key, BPM, etc.

    Args:
        conn: Database connection
        limit: Maximum number of samples (None for all)
        offset: Number of samples to skip

    Returns:
        List of dictionaries with metadata only (no chord data)
    """
    query = """
        SELECT id, filepath, filename, directory,
               estimated_key, estimated_bpm, duration_seconds,
               time_signature, first_beat_offset
        FROM samples
        ORDER BY filename
    """
    if limit is not None:
        query += f" LIMIT {limit} OFFSET {offset}"

    cursor = conn.execute(query)
    rows = cursor.fetchall()

    return [
        {
            'id': row['id'],
            'filepath': row['filepath'],
            'filename': row['filename'],
            'directory': row['directory'],
            'estimated_key': row['estimated_key'],
            'estimated_bpm': row['estimated_bpm'],
            'duration_seconds': row['duration_seconds'],
            'time_signature': row['time_signature'],
            'first_beat_offset': row['first_beat_offset'],
        }
        for row in rows
    ]


def find_compatible_samples(
    conn: sqlite3.Connection,
    target_filepath: str,
    min_score: float = 50.0,
    limit: int = 20,
    use_cache: bool = True,
    use_rhythm: bool = False,
) -> List[CompatibilityResult]:
    """
    Find samples compatible with a target sample.

    Args:
        conn: Database connection
        target_filepath: Path to the target sample
        min_score: Minimum compatibility score (0-100)
        limit: Maximum number of results
        use_cache: Whether to use cached compatibility scores
        use_rhythm: Whether to include rhythm pattern comparison (requires beat info)

    Returns:
        List of CompatibilityResult objects, sorted by score descending
    """
    # Get target sample
    target = get_sample_by_filepath(conn, target_filepath)
    if not target:
        return []

    target_progression = target.progression
    target_has_beats = target.has_beat_info

    # Get all other samples
    cursor = conn.execute(
        "SELECT * FROM samples WHERE filepath != ?",
        (target_filepath,),
    )

    results = []

    for row in cursor:
        sample = _row_to_sample(row)

        # Check cache first if enabled (only for non-rhythm comparisons)
        cached = None
        if use_cache and not use_rhythm and target.id and sample.id:
            cached = _get_cached_compatibility(conn, target.id, sample.id)

        if cached:
            score = cached["score"]
            components = cached["components"]
            reasons = cached["reasons"]
        else:
            # Calculate compatibility
            # Use rhythm comparison if enabled and both samples have beat info
            if use_rhythm and target_has_beats and sample.has_beat_info:
                # Include tempo compatibility if both samples have BPM
                compat = calculate_compatibility_with_rhythm(
                    target.chords,
                    sample.chords,
                    bpm_a=target.estimated_bpm,
                    bpm_b=sample.estimated_bpm,
                )
            else:
                compat = calculate_compatibility(target_progression, sample.progression)

            score = compat["overall"]
            components = compat.get("components", {})
            reasons = compat.get("reasons", [])

            # Cache the result (only for non-rhythm comparisons to avoid stale cache)
            if not use_rhythm and target.id and sample.id:
                _cache_compatibility(
                    conn, target.id, sample.id, score, components, reasons
                )

        if score >= min_score:
            results.append(
                CompatibilityResult(
                    sample=sample,
                    overall_score=score,
                    components=components,
                    reasons=reasons,
                )
            )

    # Sort by score descending
    results.sort(key=lambda x: x.overall_score, reverse=True)

    return results[:limit]


def get_database_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get statistics about the database contents.

    Args:
        conn: Database connection

    Returns:
        Dictionary with statistics
    """
    stats = {}

    # Sample count
    cursor = conn.execute("SELECT COUNT(*) FROM samples")
    stats["total_samples"] = cursor.fetchone()[0]

    # Unique keys
    cursor = conn.execute(
        "SELECT estimated_key, COUNT(*) as count FROM samples "
        "WHERE estimated_key IS NOT NULL GROUP BY estimated_key ORDER BY count DESC"
    )
    stats["keys"] = {row[0]: row[1] for row in cursor}

    # Split keys into root notes and scales
    from collections import Counter
    key_root_counter = Counter()
    scale_counter = Counter()

    cursor = conn.execute("SELECT estimated_key FROM samples WHERE estimated_key IS NOT NULL")
    for row in cursor:
        key = row[0]
        parts = key.split()
        if len(parts) >= 2:
            key_root = parts[0]  # "C", "A", "F#"
            scale = parts[1].capitalize()  # "Major", "Minor"
            key_root_counter[key_root] += 1
            scale_counter[scale] += 1
        elif len(parts) == 1:
            key_root_counter[parts[0]] += 1

    stats["key_roots"] = dict(key_root_counter.most_common())
    stats["scales"] = dict(scale_counter.most_common())

    # Chord progression patterns (top progressions based on Roman numerals)
    from . import theory
    progression_counter = Counter()

    cursor = conn.execute("SELECT estimated_key, progression_json FROM samples WHERE estimated_key IS NOT NULL AND progression_json IS NOT NULL")
    for row in cursor:
        key = row[0]
        progression_json = row[1]
        if progression_json:
            import json
            progression = json.loads(progression_json)
            # Convert to Roman numerals
            roman_numerals = []
            for chord in progression[:6]:  # Limit to first 6 chords to keep patterns manageable
                roman = theory.chord_to_roman_numeral(chord, key)
                if roman and roman != "?":
                    roman_numerals.append(roman)

            if len(roman_numerals) >= 2:  # Only count progressions with at least 2 chords
                pattern = " → ".join(roman_numerals)
                progression_counter[pattern] += 1

    # Get top 10 progressions
    stats["chord_progressions"] = dict(progression_counter.most_common(10))

    # Average duration
    cursor = conn.execute("SELECT AVG(duration_seconds) FROM samples")
    avg = cursor.fetchone()[0]
    stats["avg_duration"] = round(avg, 2) if avg else 0

    # BPM statistics
    cursor = conn.execute(
        "SELECT MIN(estimated_bpm), MAX(estimated_bpm), AVG(estimated_bpm) "
        "FROM samples WHERE estimated_bpm IS NOT NULL"
    )
    row = cursor.fetchone()
    if row and row[0] is not None:
        stats["bpm_min"] = round(row[0], 1)
        stats["bpm_max"] = round(row[1], 1)
        stats["bpm_avg"] = round(row[2], 1)

    # Samples with tempo info
    cursor = conn.execute(
        "SELECT COUNT(*) FROM samples WHERE estimated_bpm IS NOT NULL"
    )
    stats["samples_with_tempo"] = cursor.fetchone()[0]

    # Tempo distribution (10 BPM buckets)
    tempo_distribution = {}
    cursor = conn.execute("SELECT estimated_bpm FROM samples WHERE estimated_bpm IS NOT NULL")
    for row in cursor:
        bpm = row[0]
        # Create bucket (e.g., 60-69, 70-79, 80-89)
        bucket_start = int(bpm // 10) * 10
        bucket_label = f"{bucket_start}-{bucket_start + 9}"
        tempo_distribution[bucket_label] = tempo_distribution.get(bucket_label, 0) + 1

    # Sort by bucket start value
    stats["tempo_distribution"] = dict(sorted(
        tempo_distribution.items(),
        key=lambda x: int(x[0].split('-')[0])
    ))

    # Time signature distribution
    cursor = conn.execute(
        "SELECT time_signature, COUNT(*) as count FROM samples "
        "WHERE time_signature IS NOT NULL GROUP BY time_signature ORDER BY count DESC"
    )
    stats["time_signatures"] = {row[0]: row[1] for row in cursor}

    # Cache stats
    cursor = conn.execute("SELECT COUNT(*) FROM compatibility_cache")
    stats["cached_comparisons"] = cursor.fetchone()[0]

    return stats


def clear_compatibility_cache(conn: sqlite3.Connection) -> int:
    """
    Clear all cached compatibility scores.

    Args:
        conn: Database connection

    Returns:
        Number of cache entries deleted
    """
    cursor = conn.execute("DELETE FROM compatibility_cache")
    conn.commit()
    return cursor.rowcount


def _row_to_sample(row: sqlite3.Row) -> Sample:
    """Convert a database row to a Sample object."""
    chords_data = json.loads(row["chords_json"]) if row["chords_json"] else []
    chords = [ChordEvent.from_dict(c) for c in chords_data]

    # Parse time signature string (e.g., "4/4" -> (4, 4))
    time_sig_str = row["time_signature"] if "time_signature" in row.keys() else "4/4"
    if time_sig_str and "/" in time_sig_str:
        parts = time_sig_str.split("/")
        time_signature = (int(parts[0]), int(parts[1]))
    else:
        time_signature = (4, 4)

    first_beat_offset = row["first_beat_offset"] if "first_beat_offset" in row.keys() else 0.0
    voicing_type = row["voicing_type"] if "voicing_type" in row.keys() else None

    return Sample(
        id=row["id"],
        filepath=row["filepath"],
        filename=row["filename"],
        chords=chords,
        duration_seconds=row["duration_seconds"] or 0.0,
        estimated_key=row["estimated_key"],
        estimated_bpm=row["estimated_bpm"],
        time_signature=time_signature,
        first_beat_offset=first_beat_offset or 0.0,
        voicing_type=voicing_type,
    )


def _get_cached_compatibility(
    conn: sqlite3.Connection, sample_a_id: int, sample_b_id: int
) -> Optional[Dict[str, Any]]:
    """Get cached compatibility score between two samples."""
    # Check both orderings
    cursor = conn.execute(
        """
        SELECT score, components_json, reasons_json FROM compatibility_cache
        WHERE (sample_a_id = ? AND sample_b_id = ?)
           OR (sample_a_id = ? AND sample_b_id = ?)
    """,
        (sample_a_id, sample_b_id, sample_b_id, sample_a_id),
    )
    row = cursor.fetchone()

    if not row:
        return None

    return {
        "score": row["score"],
        "components": json.loads(row["components_json"]) if row["components_json"] else {},
        "reasons": json.loads(row["reasons_json"]) if row["reasons_json"] else [],
    }


def _cache_compatibility(
    conn: sqlite3.Connection,
    sample_a_id: int,
    sample_b_id: int,
    score: float,
    components: Dict[str, float],
    reasons: List[str],
) -> None:
    """Cache a compatibility score."""
    conn.execute(
        """
        INSERT OR REPLACE INTO compatibility_cache
        (sample_a_id, sample_b_id, score, components_json, reasons_json)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            sample_a_id,
            sample_b_id,
            score,
            json.dumps(components),
            json.dumps(reasons),
        ),
    )
    conn.commit()


# =============================================================================
# Pitch Analysis Cache Functions
# =============================================================================


def cache_pitch_analysis(
    conn: sqlite3.Connection,
    result: PitchAnalysisResult,
) -> int:
    """
    Store pitch analysis result in cache.

    Args:
        conn: Database connection
        result: PitchAnalysisResult to cache

    Returns:
        ID of the cached entry
    """
    notes_data = [n.to_dict() for n in result.notes]

    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO pitch_analysis_cache
        (filepath, file_hash, notes_json, is_monophonic, polyphony_level,
         detected_bpm, duration_seconds, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        (
            result.filepath,
            result.file_hash or "",
            json.dumps(notes_data),
            result.is_monophonic,
            result.polyphony_level,
            result.detected_bpm,
            result.duration_seconds,
        ),
    )

    conn.commit()
    return cursor.lastrowid


def get_cached_pitch_analysis(
    conn: sqlite3.Connection,
    filepath: str,
    file_hash: Optional[str] = None,
) -> Optional[PitchAnalysisResult]:
    """
    Retrieve cached pitch analysis if valid.

    If file_hash is provided, only returns cache if hash matches
    (i.e., file hasn't changed since analysis).

    Args:
        conn: Database connection
        filepath: Path to audio file
        file_hash: Optional current file hash for validation

    Returns:
        PitchAnalysisResult or None if not cached or invalid
    """
    cursor = conn.execute(
        "SELECT * FROM pitch_analysis_cache WHERE filepath = ?",
        (filepath,),
    )
    row = cursor.fetchone()

    if not row:
        return None

    # If file_hash provided, validate cache
    if file_hash and row["file_hash"] != file_hash:
        # Cache is stale, delete it
        conn.execute(
            "DELETE FROM pitch_analysis_cache WHERE filepath = ?",
            (filepath,),
        )
        conn.commit()
        return None

    # Parse notes from JSON
    notes_data = json.loads(row["notes_json"]) if row["notes_json"] else []
    notes = [NoteEvent.from_dict(n) for n in notes_data]

    return PitchAnalysisResult(
        filepath=row["filepath"],
        notes=notes,
        duration_seconds=row["duration_seconds"] or 0.0,
        is_monophonic=bool(row["is_monophonic"]),
        polyphony_level=row["polyphony_level"] or 1,
        detected_bpm=row["detected_bpm"],
        file_hash=row["file_hash"],
    )


def invalidate_pitch_cache(
    conn: sqlite3.Connection,
    filepath: str,
) -> bool:
    """
    Invalidate (delete) cached pitch analysis for a file.

    Args:
        conn: Database connection
        filepath: Path to audio file

    Returns:
        True if cache entry was deleted, False if not found
    """
    cursor = conn.execute(
        "DELETE FROM pitch_analysis_cache WHERE filepath = ?",
        (filepath,),
    )
    conn.commit()
    return cursor.rowcount > 0


def clear_pitch_cache(conn: sqlite3.Connection) -> int:
    """
    Clear all cached pitch analysis results.

    Args:
        conn: Database connection

    Returns:
        Number of cache entries deleted
    """
    cursor = conn.execute("DELETE FROM pitch_analysis_cache")
    conn.commit()
    return cursor.rowcount


def get_pitch_cache_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get statistics about the pitch analysis cache.

    Args:
        conn: Database connection

    Returns:
        Dictionary with cache statistics
    """
    stats = {}

    # Total cached entries
    cursor = conn.execute("SELECT COUNT(*) FROM pitch_analysis_cache")
    stats["cached_files"] = cursor.fetchone()[0]

    # Monophonic vs polyphonic
    cursor = conn.execute(
        "SELECT is_monophonic, COUNT(*) FROM pitch_analysis_cache GROUP BY is_monophonic"
    )
    for row in cursor:
        if row[0]:
            stats["monophonic_count"] = row[1]
        else:
            stats["polyphonic_count"] = row[1]

    # Average polyphony level
    cursor = conn.execute(
        "SELECT AVG(polyphony_level) FROM pitch_analysis_cache WHERE NOT is_monophonic"
    )
    avg = cursor.fetchone()[0]
    stats["avg_polyphony"] = round(avg, 2) if avg else 0

    # Total notes cached
    cursor = conn.execute("SELECT notes_json FROM pitch_analysis_cache")
    total_notes = 0
    for row in cursor:
        if row[0]:
            notes = json.loads(row[0])
            total_notes += len(notes)
    stats["total_notes_cached"] = total_notes

    return stats
