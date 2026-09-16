#!/usr/bin/env python3
"""
Database migration script to add voicing_type column and detect voicing for existing samples.

This script:
1. Adds the voicing_type column to the samples table (if not exists)
2. Loads all existing samples
3. Detects voicing type (monophonic/polyphonic/ambiguous) for each
4. Updates the database with voicing classifications

Run with: python3 migrate_add_voicing_type.py <database_path>
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from chord_analyzer.database import init_database, get_all_samples
from chord_analyzer.voicing import detect_voicing_type, VoicingType


def add_voicing_column(db_path: str) -> None:
    """Add voicing_type column to samples table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column exists
    cursor.execute("PRAGMA table_info(samples)")
    columns = [row[1] for row in cursor.fetchall()]

    if "voicing_type" not in columns:
        print("Adding voicing_type column to samples table...")
        cursor.execute("ALTER TABLE samples ADD COLUMN voicing_type TEXT")
        conn.commit()
        print("✓ Column added successfully")
    else:
        print("ℹ️  voicing_type column already exists")

    conn.close()


def detect_and_update_voicing(db_path: str, dry_run: bool = False) -> Tuple[int, int, dict]:
    """
    Detect and update voicing type for all samples.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, don't actually update the database

    Returns:
        Tuple of (total_samples, samples_updated, voicing_stats)
    """
    conn = init_database(db_path)
    cursor = conn.cursor()

    # Get all samples
    samples = get_all_samples(conn)
    total_samples = len(samples)

    if total_samples == 0:
        print("No samples found in database.")
        return 0, 0, {}

    print(f"\nAnalyzing {total_samples} samples...")
    print("-" * 80)

    voicing_stats = {
        VoicingType.MONOPHONIC.value: 0,
        VoicingType.POLYPHONIC.value: 0,
        VoicingType.AMBIGUOUS.value: 0,
        VoicingType.UNKNOWN.value: 0,
    }

    samples_updated = 0

    for i, sample in enumerate(samples, 1):
        # Detect voicing type
        analysis = detect_voicing_type(sample)
        voicing_type = analysis.voicing_type.value

        # Update statistics
        voicing_stats[voicing_type] += 1

        # Show progress for significant classifications
        if i <= 20 or (i % 100 == 0):
            conf_str = f"{analysis.confidence*100:.0f}%" if analysis.confidence > 0 else "N/A"
            print(f"  {i}/{total_samples}: {sample.filename[:50]}")
            print(f"    → {voicing_type.upper()} (confidence: {conf_str})")
            if analysis.reasons:
                print(f"    → {analysis.reasons[0]}")

        # Update database
        if not dry_run:
            cursor.execute(
                "UPDATE samples SET voicing_type = ? WHERE id = ?",
                (voicing_type, sample.id)
            )
            samples_updated += 1

    if not dry_run:
        conn.commit()
        print(f"\n✓ Database updated with voicing classifications")
    else:
        print(f"\n[DRY RUN] No changes made to database")

    conn.close()

    return total_samples, samples_updated, voicing_stats


def main():
    parser = argparse.ArgumentParser(
        description="Add voicing_type column and classify existing samples"
    )
    parser.add_argument(
        "database",
        help="Path to SQLite database file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be classified without making changes"
    )

    args = parser.parse_args()

    # Check database exists
    if not Path(args.database).exists():
        print(f"Error: Database file not found: {args.database}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"Voicing Type Migration Script")
    print(f"{'='*80}")
    print(f"Database: {args.database}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")

    # Step 1: Add column
    add_voicing_column(args.database)

    # Step 2: Detect and update voicing
    total, updated, stats = detect_and_update_voicing(args.database, args.dry_run)

    # Print summary
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"{'='*80}")
    print(f"Total samples: {total}")
    print(f"Samples analyzed: {updated}")
    print(f"\nVoicing Distribution:")
    for voicing, count in sorted(stats.items()):
        percentage = (count / total * 100) if total > 0 else 0
        print(f"  {voicing.upper()}: {count} ({percentage:.1f}%)")

    if args.dry_run:
        print(f"\n⚠️  This was a dry run. Run without --dry-run to apply changes.")
    else:
        print(f"\n✓ Migration complete!")

    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
