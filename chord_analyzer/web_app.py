"""
Streamlit Web UI for Chord Analysis & Sample Compatibility Matcher.

Run with: streamlit run chord_analyzer/web_app.py
"""

import streamlit as st
from pathlib import Path
from typing import Optional
import os

# Import chord analyzer modules
from chord_analyzer.database import (
    init_database,
    get_all_samples,
    get_sample_by_filepath,
    find_compatible_samples,
    get_database_stats,
)
from chord_analyzer.compatibility import calculate_compatibility
from chord_analyzer.extractor import create_sample_from_csv, create_sample_from_csv_with_tempo
from chord_analyzer.filename_parser import parse_filename


# Page config
st.set_page_config(
    page_title="Chord Analyzer",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db_connection(db_path: str = "samples.db"):
    """Get or create database connection."""
    if "db_conn" not in st.session_state or st.session_state.db_path != db_path:
        st.session_state.db_conn = init_database(db_path)
        st.session_state.db_path = db_path
    return st.session_state.db_conn


def render_sidebar():
    """Render the sidebar navigation."""
    st.sidebar.title("🎵 Chord Analyzer")

    # Database selection
    st.sidebar.subheader("Database")
    db_path = st.sidebar.text_input("Database Path", value="samples.db")

    if Path(db_path).exists():
        st.sidebar.success(f"Connected: {db_path}")
    else:
        st.sidebar.warning("Database not found")

    st.sidebar.divider()

    # Navigation
    st.sidebar.subheader("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Sample Browser", "Find Compatible", "Compare Samples"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()
    st.sidebar.markdown(
        '<a href="https://github.com/geoffmyers/chord-analysis" '
        'target="_blank" rel="noopener noreferrer" '
        'style="display:inline-flex;align-items:center;gap:6px;'
        'text-decoration:none;">'
        '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" '
        'focusable="false" fill="currentColor">'
        '<path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55'
        '-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65'
        '-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67'
        '-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2'
        '-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06'
        ' 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15'
        '-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 '
        '1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 '
        '1 0 8c0-4.42 3.58-8 8-8Z"></path></svg>'
        "<span>View source on GitHub</span></a>",
        unsafe_allow_html=True,
    )

    return db_path, page


def render_dashboard(db_path: str):
    """Render the dashboard page with database statistics."""
    st.title("Dashboard")

    if not Path(db_path).exists():
        st.warning("No database found. Use the CLI to analyze samples first.")
        st.code("python -m chord_analyzer analyze --csv-dir ./chord_data --db samples.db")
        return

    conn = get_db_connection(db_path)
    stats = get_database_stats(conn)

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Samples", stats["total_samples"])

    with col2:
        st.metric("Avg Duration", f"{stats['avg_duration']}s")

    with col3:
        tempo_count = stats.get("samples_with_tempo", 0)
        st.metric("With Tempo", tempo_count)

    with col4:
        st.metric("Cached Comparisons", stats["cached_comparisons"])

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Samples by Key")
        if stats.get("keys"):
            import pandas as pd
            keys_df = pd.DataFrame(
                list(stats["keys"].items()),
                columns=["Key", "Count"]
            ).head(10)
            st.bar_chart(keys_df.set_index("Key"))
        else:
            st.info("No key data available")

    with col2:
        st.subheader("Time Signatures")
        if stats.get("time_signatures"):
            import pandas as pd
            ts_df = pd.DataFrame(
                list(stats["time_signatures"].items()),
                columns=["Time Sig", "Count"]
            )
            st.bar_chart(ts_df.set_index("Time Sig"))
        else:
            st.info("No time signature data")

    # BPM stats
    if stats.get("bpm_min"):
        st.subheader("Tempo Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Min BPM", stats["bpm_min"])
        with col2:
            st.metric("Avg BPM", stats["bpm_avg"])
        with col3:
            st.metric("Max BPM", stats["bpm_max"])


def render_sample_browser(db_path: str):
    """Render the sample browser page."""
    st.title("Sample Browser")

    if not Path(db_path).exists():
        st.warning("No database found.")
        return

    conn = get_db_connection(db_path)
    samples = get_all_samples(conn)

    if not samples:
        st.info("No samples in database.")
        return

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        # Key filter
        all_keys = sorted(set(s.estimated_key for s in samples if s.estimated_key))
        key_filter = st.selectbox("Filter by Key", ["All"] + all_keys)

    with col2:
        # BPM range filter
        bpms = [s.estimated_bpm for s in samples if s.estimated_bpm]
        if bpms:
            min_bpm, max_bpm = int(min(bpms)), int(max(bpms))
            bpm_range = st.slider("BPM Range", min_bpm, max_bpm, (min_bpm, max_bpm))
        else:
            bpm_range = None

    with col3:
        # Search
        search = st.text_input("Search filename")

    # Apply filters
    filtered = samples
    if key_filter != "All":
        filtered = [s for s in filtered if s.estimated_key == key_filter]
    if bpm_range:
        filtered = [s for s in filtered if s.estimated_bpm and bpm_range[0] <= s.estimated_bpm <= bpm_range[1]]
    if search:
        filtered = [s for s in filtered if search.lower() in s.filename.lower()]

    st.caption(f"Showing {len(filtered)} of {len(samples)} samples")

    # Display samples
    for sample in filtered[:50]:  # Limit display
        with st.expander(f"🎵 {sample.filename}", expanded=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write(f"**Progression:** {' → '.join(sample.progression[:8])}")
                if len(sample.progression) > 8:
                    st.caption(f"... and {len(sample.progression) - 8} more chords")

            with col2:
                if sample.estimated_key:
                    st.write(f"**Key:** {sample.estimated_key}")
                if sample.estimated_bpm:
                    st.write(f"**BPM:** {sample.estimated_bpm}")
                st.write(f"**Duration:** {sample.duration_seconds:.1f}s")

            # Details
            st.caption(f"Root notes: {', '.join(sorted(sample.root_notes))}")
            st.caption(f"Chord types: {', '.join(sorted(sample.chord_types))}")

            # Action buttons
            if st.button("Find Compatible", key=f"find_{sample.id}"):
                st.session_state.target_sample = sample.filepath
                st.session_state.page = "Find Compatible"
                st.rerun()


def render_find_compatible(db_path: str):
    """Render the compatibility finder page."""
    st.title("Find Compatible Samples")

    if not Path(db_path).exists():
        st.warning("No database found.")
        return

    conn = get_db_connection(db_path)
    samples = get_all_samples(conn)

    if not samples:
        st.info("No samples in database.")
        return

    # Target sample selection
    sample_options = {s.filename: s.filepath for s in samples}

    # Check if we have a pre-selected target
    default_idx = 0
    if "target_sample" in st.session_state:
        target_path = st.session_state.target_sample
        for idx, (name, path) in enumerate(sample_options.items()):
            if path == target_path:
                default_idx = idx
                break

    selected_name = st.selectbox(
        "Select Target Sample",
        list(sample_options.keys()),
        index=default_idx,
    )
    target_path = sample_options[selected_name]

    # Options
    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 50)
    with col2:
        limit = st.slider("Max Results", 5, 50, 20)
    with col3:
        use_rhythm = st.checkbox("Use Rhythm Comparison")

    # Find button
    if st.button("🔍 Find Compatible Samples", type="primary"):
        with st.spinner("Searching..."):
            results = find_compatible_samples(
                conn,
                target_path,
                min_score=min_score,
                limit=limit,
                use_rhythm=use_rhythm,
            )

        if not results:
            st.warning(f"No matches found with score >= {min_score}")
        else:
            st.success(f"Found {len(results)} compatible samples")

            # Display results
            for i, result in enumerate(results, 1):
                score_color = "green" if result.overall_score >= 70 else "orange" if result.overall_score >= 50 else "red"

                with st.expander(
                    f"#{i} {result.sample.filename} — Score: {result.overall_score:.1f}",
                    expanded=(i <= 3),
                ):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write(f"**Progression:** {' → '.join(result.sample.progression[:6])}")

                        # Score breakdown
                        if result.components:
                            st.write("**Score Components:**")
                            for comp, val in result.components.items():
                                if val != 0:
                                    st.write(f"  • {comp}: {val:.1f}")

                    with col2:
                        if result.sample.estimated_key:
                            st.write(f"**Key:** {result.sample.estimated_key}")
                        if result.sample.estimated_bpm:
                            st.write(f"**BPM:** {result.sample.estimated_bpm}")

                    # Reasons
                    if result.reasons:
                        st.caption("💡 " + "; ".join(result.reasons))


def render_compare_samples(db_path: str):
    """Render the sample comparison page."""
    st.title("Compare Samples")

    if not Path(db_path).exists():
        st.warning("No database found.")
        return

    conn = get_db_connection(db_path)
    samples = get_all_samples(conn)

    if len(samples) < 2:
        st.info("Need at least 2 samples to compare.")
        return

    sample_options = {s.filename: s for s in samples}

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sample A")
        name_a = st.selectbox("Select Sample A", list(sample_options.keys()), key="sample_a")
        sample_a = sample_options[name_a]

        st.write(f"**Key:** {sample_a.estimated_key or 'Unknown'}")
        st.write(f"**BPM:** {sample_a.estimated_bpm or 'Unknown'}")
        st.write(f"**Progression:** {' → '.join(sample_a.progression[:6])}")

    with col2:
        st.subheader("Sample B")
        # Default to different sample
        other_names = [n for n in sample_options.keys() if n != name_a]
        name_b = st.selectbox("Select Sample B", other_names, key="sample_b")
        sample_b = sample_options[name_b]

        st.write(f"**Key:** {sample_b.estimated_key or 'Unknown'}")
        st.write(f"**BPM:** {sample_b.estimated_bpm or 'Unknown'}")
        st.write(f"**Progression:** {' → '.join(sample_b.progression[:6])}")

    st.divider()

    # Compare button
    if st.button("⚖️ Compare", type="primary"):
        result = calculate_compatibility(sample_a.progression, sample_b.progression)

        # Overall score
        score = result["overall"]
        if score >= 70:
            st.success(f"### Compatibility Score: {score:.1f}/100")
        elif score >= 50:
            st.warning(f"### Compatibility Score: {score:.1f}/100")
        else:
            st.error(f"### Compatibility Score: {score:.1f}/100")

        # Transposition info
        if result.get("is_transposition"):
            interval = result.get("transposition_interval", 0)
            note = result.get("transposition_note", "")
            st.info(f"🎹 These are transpositions of each other! (Interval: {interval} semitones / {note})")

        # Score breakdown
        st.subheader("Score Breakdown")

        components = result.get("components", {})
        cols = st.columns(len(components))

        for col, (comp, val) in zip(cols, components.items()):
            with col:
                display_name = comp.replace("_", " ").title()
                if val >= 0:
                    st.metric(display_name, f"+{val:.1f}")
                else:
                    st.metric(display_name, f"{val:.1f}")

        # Reasons
        if result.get("reasons"):
            st.subheader("Analysis")
            for reason in result["reasons"]:
                st.write(f"• {reason}")


def main():
    """Main entry point for the Streamlit app."""
    db_path, page = render_sidebar()

    if page == "Dashboard":
        render_dashboard(db_path)
    elif page == "Sample Browser":
        render_sample_browser(db_path)
    elif page == "Find Compatible":
        render_find_compatible(db_path)
    elif page == "Compare Samples":
        render_compare_samples(db_path)


if __name__ == "__main__":
    main()
