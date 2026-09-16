"""Tests for database operations."""

import pytest
import tempfile
import os
from pathlib import Path

from chord_analyzer.database import (
    init_database,
    store_sample,
    get_sample_by_filepath,
    get_sample_by_id,
    get_all_samples,
    get_database_stats,
    clear_compatibility_cache,
)
from chord_analyzer.models import ChordEvent, Sample


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = init_database(db_path)
    yield conn, db_path

    conn.close()
    os.unlink(db_path)


@pytest.fixture
def sample_data():
    """Create sample test data."""
    chords = [
        ChordEvent(0.5, 2.0, "C:maj", "C", "maj"),
        ChordEvent(2.0, 3.5, "A:min", "A", "min"),
        ChordEvent(3.5, 4.0, "F:maj", "F", "maj"),
        ChordEvent(4.0, 5.5, "G:7", "G", "7"),
    ]

    return Sample(
        filepath="/path/to/sample.wav",
        filename="sample",
        chords=chords,
        duration_seconds=5.5,
        estimated_key="C",
        estimated_bpm=120.0,
    )


class TestInitDatabase:
    """Tests for database initialization."""

    def test_creates_tables(self, temp_db):
        """Test that required tables are created."""
        conn, _ = temp_db

        # Check samples table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='samples'"
        )
        assert cursor.fetchone() is not None

        # Check compatibility_cache table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='compatibility_cache'"
        )
        assert cursor.fetchone() is not None

    def test_idempotent(self, temp_db):
        """Test that init can be called multiple times safely."""
        conn, db_path = temp_db

        # Initialize again
        conn2 = init_database(db_path)
        conn2.close()

        # Should not raise any errors


class TestStoreSample:
    """Tests for storing samples."""

    def test_store_and_retrieve(self, temp_db, sample_data):
        """Test storing and retrieving a sample."""
        conn, _ = temp_db

        sample_id = store_sample(conn, sample_data)
        assert sample_id > 0

        retrieved = get_sample_by_filepath(conn, sample_data.filepath)
        assert retrieved is not None
        assert retrieved.filename == "sample"
        assert len(retrieved.chords) == 4
        assert retrieved.estimated_key == "C"

    def test_upsert(self, temp_db, sample_data):
        """Test that storing same filepath updates the record."""
        conn, _ = temp_db

        # Store once
        id1 = store_sample(conn, sample_data)

        # Modify and store again
        sample_data.estimated_key = "G"
        id2 = store_sample(conn, sample_data)

        # Should be same record (upsert)
        retrieved = get_sample_by_filepath(conn, sample_data.filepath)
        assert retrieved.estimated_key == "G"

    def test_chord_serialization(self, temp_db, sample_data):
        """Test that chords are properly serialized and deserialized."""
        conn, _ = temp_db

        store_sample(conn, sample_data)
        retrieved = get_sample_by_filepath(conn, sample_data.filepath)

        assert len(retrieved.chords) == 4
        assert retrieved.chords[0].chord_label == "C:maj"
        assert retrieved.chords[0].start_time == 0.5
        assert retrieved.chords[0].end_time == 2.0


class TestGetSample:
    """Tests for retrieving samples."""

    def test_get_by_filepath(self, temp_db, sample_data):
        """Test getting sample by filepath."""
        conn, _ = temp_db
        store_sample(conn, sample_data)

        result = get_sample_by_filepath(conn, sample_data.filepath)
        assert result is not None
        assert result.filepath == sample_data.filepath

    def test_get_by_filepath_not_found(self, temp_db):
        """Test getting non-existent sample."""
        conn, _ = temp_db

        result = get_sample_by_filepath(conn, "/nonexistent/path.wav")
        assert result is None

    def test_get_by_id(self, temp_db, sample_data):
        """Test getting sample by ID."""
        conn, _ = temp_db
        sample_id = store_sample(conn, sample_data)

        result = get_sample_by_id(conn, sample_id)
        assert result is not None
        assert result.id == sample_id

    def test_get_all_samples(self, temp_db):
        """Test getting all samples."""
        conn, _ = temp_db

        # Store multiple samples
        for i in range(3):
            sample = Sample(
                filepath=f"/path/to/sample_{i}.wav",
                filename=f"sample_{i}",
                chords=[ChordEvent(0, 1, "C:maj", "C", "maj")],
                duration_seconds=1.0,
            )
            store_sample(conn, sample)

        samples = get_all_samples(conn)
        assert len(samples) == 3


class TestDatabaseStats:
    """Tests for database statistics."""

    def test_empty_database(self, temp_db):
        """Test stats on empty database."""
        conn, _ = temp_db

        stats = get_database_stats(conn)
        assert stats["total_samples"] == 0
        assert stats["avg_duration"] == 0

    def test_with_samples(self, temp_db, sample_data):
        """Test stats with samples."""
        conn, _ = temp_db

        store_sample(conn, sample_data)
        sample_data.filepath = "/path/to/sample2.wav"
        sample_data.duration_seconds = 10.0
        store_sample(conn, sample_data)

        stats = get_database_stats(conn)
        assert stats["total_samples"] == 2
        assert stats["avg_duration"] > 0


class TestCompatibilityCache:
    """Tests for compatibility caching."""

    def test_clear_cache(self, temp_db):
        """Test clearing the compatibility cache."""
        conn, _ = temp_db

        # Add some cache entries manually
        conn.execute(
            """
            INSERT INTO samples (filepath, filename, duration_seconds)
            VALUES (?, ?, ?), (?, ?, ?)
        """,
            ("/a.wav", "a", 1.0, "/b.wav", "b", 1.0),
        )
        conn.execute(
            """
            INSERT INTO compatibility_cache (sample_a_id, sample_b_id, score)
            VALUES (1, 2, 75.5)
        """
        )
        conn.commit()

        deleted = clear_compatibility_cache(conn)
        assert deleted == 1

        # Verify cache is empty
        cursor = conn.execute("SELECT COUNT(*) FROM compatibility_cache")
        assert cursor.fetchone()[0] == 0
