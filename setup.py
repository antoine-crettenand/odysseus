"""
Setup script for Odysseus Music Discovery Tool
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="odysseus",
    version="1.0.0",
    author="Odysseus Team",
    author_email="contact@example.com",
    description="Music Discovery Tool - Search MusicBrainz, find YouTube videos, and download music",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/antoinecrettenand/odysseus",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
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
