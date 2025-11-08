"""
Setup script for Odysseus Music Discovery Tool
"""

import sys

try:
    from setuptools import setup, find_packages
except ImportError:
    print("ERROR: setuptools is not installed.")
    print("\nPlease install setuptools first:")
    print("  pip install setuptools")
    print("\nOr better yet, use pip to install this package directly:")
    print("  pip install -e .")
    print("\nThis will automatically handle all dependencies including setuptools.")
    raise SystemExit(1)

from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Check if setup.py is being run without arguments
if len(sys.argv) == 1:
    print("=" * 70)
    print("NOTE: You're running setup.py without any commands.")
    print("=" * 70)
    print("\nThe recommended way to install this package is:")
    print("  pip install -e .")
    print("\nThis will install the package in development mode and handle")
    print("all dependencies automatically.")
    print("\nIf you need to use setup.py directly, try:")
    print("  python setup.py --help")
    print("  python setup.py install")
    print("\n" + "=" * 70)
    sys.exit(0)

setup(
    name="odysseus",
    version="1.0.0",
    author="Odysseus Team",
    author_email="contact@example.com",
    description="Music Discovery Tool - Search MusicBrainz, find YouTube videos, and download music",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/antoinecrettenand/odysseus",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "mutagen>=1.45.0",
        "yt-dlp>=2023.12.30",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
    },
    entry_points={
        "console_scripts": [
            "odysseus=odysseus.main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
