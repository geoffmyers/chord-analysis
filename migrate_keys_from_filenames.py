#!/usr/bin/env python3
"""
Database migration script to update sample keys based on filename parsing.

This script:
1. Scans all samples in the database
2. Parses filenames to extract key signatures
3. Updates samples where filename key differs from stored key
4. Reports statistics on updates made

Run with: python3 migrate_keys_from_filenames.py <database_path>
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from chord_analyzer.filename_parser import parse_filename


def get_sample_count(conn: sqlite3.Connection) -> int:
    """Get total number of samples in database."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM samples")
    return cursor.fetchone()[0]


def update_sample_key(
    conn: sqlite3.Connection,
    sample_id: int,
    new_key: str,
) -> None:
    """Update the estimated_key for a sample."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE samples SET estimated_key = ? WHERE id = ?",
        (new_key, sample_id)
    )


def migrate_keys(db_path: str, dry_run: bool = False) -> Tuple[int, int, int]:
    """
    Migrate sample keys based on filename parsing.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, don't actually update the database

    Returns:
        Tuple of (total_samples, samples_with_filename_keys, samples_updated)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all samples
    cursor.execute("SELECT id, filename, filepath, estimated_key FROM samples")
    samples = cursor.fetchall()

    total_samples = len(samples)
    samples_with_filename_keys = 0
    samples_updated = 0

    print(f"\nScanning {total_samples} samples...")
    print("-" * 80)

    for sample_id, filename, filepath, current_key in samples:
        # Use filepath if available, otherwise filename
        parse_path = filepath if filepath else filename

        # Parse filename for key
        filename_info = parse_filename(parse_path)

        if filename_info.has_key:
            samples_with_filename_keys += 1
            filename_key = filename_info.key

            # Check if key differs from current
            if filename_key != current_key:
                samples_updated += 1

                print(f"\nSample ID {sample_id}: {filename}")
                print(f"  Current key: {current_key}")
                print(f"  Filename key: {filename_key}")

                if not dry_run:
                    update_sample_key(conn, sample_id, filename_key)
                    print(f"  ✓ Updated to: {filename_key}")
                else:
                    print(f"  [DRY RUN] Would update to: {filename_key}")

    if not dry_run:
        conn.commit()
        print(f"\n✓ Changes committed to database")
    else:
        print(f"\n[DRY RUN] No changes made to database")

    conn.close()

    return total_samples, samples_with_filename_keys, samples_updated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate sample keys in database based on filename parsing"
    )
    parser.add_argument(
        "database",
        help="Path to SQLite database file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )

    args = parser.parse_args()

    # Check database exists
    if not Path(args.database).exists():
        print(f"Error: Database file not found: {args.database}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"Key Signature Migration Script")
    print(f"{'='*80}")
    print(f"Database: {args.database}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")

    # Run migration
    total, with_keys, updated = migrate_keys(args.database, args.dry_run)

    # Print summary
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"{'='*80}")
    print(f"Total samples: {total}")
    print(f"Samples with filename keys: {with_keys} ({100*with_keys/total:.1f}%)")
    print(f"Samples updated: {updated} ({100*updated/total:.1f}%)")
    print(f"Samples unchanged: {total - updated}")

    if args.dry_run:
        print(f"\n⚠️  This was a dry run. Run without --dry-run to apply changes.")
    else:
        print(f"\n✓ Migration complete!")

    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
