"""Setup script for chord-analyzer package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="chord-analyzer",
    version="0.1.0",
    author="Geoff Myers",
    license="GPL-3.0-or-later",
    description="Analyze chord progressions and find harmonically compatible samples",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "rich>=13.0.0",
    ],
    extras_require={
        "audio": ["pydub>=0.25.0"],
        "web": ["streamlit>=1.28.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "chord-analyzer=chord_analyzer.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
