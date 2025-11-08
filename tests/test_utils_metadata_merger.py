"""
Tests for metadata merger utilities.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.utils.metadata_merger import MetadataSource, MetadataMerger
from odysseus.models.song import AudioMetadata


class TestMetadataSource:
    """Tests for MetadataSource class."""
    
    def test_metadata_source_creation(self):
        """Test MetadataSource creation."""
        metadata = AudioMetadata(title="Test", artist="Artist")
        source = MetadataSource(
            source_name="test_source",
            metadata=metadata,
            confidence=0.9
        )
        
        assert source.source_name == "test_source"
        assert source.metadata == metadata
        assert source.confidence == 0.9
        assert 0.0 <= source.completeness <= 1.0
    
    def test_metadata_source_completeness_calculation(self):
        """Test completeness calculation."""
        # Full metadata
        full_metadata = AudioMetadata(
            title="Test",
            artist="Artist",
            album="Album",
            year=2020,
            genre="Rock",
            track_number=1,
            composer="Composer",
            publisher="Publisher"
        )
        source = MetadataSource("test", full_metadata)
        assert source.completeness == 1.0
        
        # Partial metadata
        partial_metadata = AudioMetadata(
            title="Test",
            artist="Artist"
        )
        source2 = MetadataSource("test", partial_metadata)
        assert source2.completeness < 1.0
        assert source2.completeness > 0.0
    
    def test_metadata_source_default_confidence(self):
        """Test default confidence value."""
        metadata = AudioMetadata(title="Test", artist="Artist")
        source = MetadataSource("test", metadata)
        assert source.confidence == 1.0


class TestMetadataMerger:
    """Tests for MetadataMerger class."""
    
    def test_metadata_merger_initialization(self):
        """Test MetadataMerger initialization."""
        merger = MetadataMerger()
        assert merger.sources == []
        assert merger.final_metadata is None
    
    def test_add_metadata_source(self):
        """Test adding metadata source."""
        merger = MetadataMerger()
        metadata = AudioMetadata(title="Test", artist="Artist")
        
        merger.add_metadata_source("source1", metadata, confidence=0.9)
        
        assert len(merger.sources) == 1
        assert merger.sources[0].source_name == "source1"
        assert merger.sources[0].metadata == metadata
        assert merger.sources[0].confidence == 0.9
    
    def test_merge_metadata_no_sources(self):
        """Test merging with no sources."""
        merger = MetadataMerger()
        result = merger.merge_metadata()
        
        assert isinstance(result, AudioMetadata)
        assert merger.final_metadata == result
    
    def test_merge_metadata_single_source(self):
        """Test merging with single source."""
        merger = MetadataMerger()
        metadata = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2020
        )
        merger.add_metadata_source("source1", metadata)
        
        result = merger.merge_metadata()
        
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.year == 2020
        assert "source1" in result.source
    
    def test_merge_metadata_multiple_sources(self):
        """Test merging with multiple sources."""
        merger = MetadataMerger()
        
        # Add first source with high confidence
        metadata1 = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2020
        )
        merger.add_metadata_source("source1", metadata1, confidence=1.0)
        
        # Add second source with missing fields
        metadata2 = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            genre="Rock"
        )
        merger.add_metadata_source("source2", metadata2, confidence=0.8)
        
        result = merger.merge_metadata()
        
        # Should use source1 as base (higher confidence * completeness)
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.year == 2020
        # Should fill genre from source2
        assert result.genre == "Rock"
    
    def test_merge_metadata_fills_missing_fields(self):
        """Test that missing fields are filled from other sources."""
        merger = MetadataMerger()
        
        # Source with missing fields
        metadata1 = AudioMetadata(
            title="Test Song",
            artist="Test Artist"
        )
        merger.add_metadata_source("source1", metadata1, confidence=1.0)
        
        # Source with additional fields
        metadata2 = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2020,
            genre="Rock"
        )
        merger.add_metadata_source("source2", metadata2, confidence=0.9)
        
        result = merger.merge_metadata()
        
        # Should have all fields
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.year == 2020
        assert result.genre == "Rock"
    
    def test_merge_metadata_confidence_threshold(self):
        """Test that low confidence sources don't fill fields."""
        merger = MetadataMerger()
        
        metadata1 = AudioMetadata(title="Test", artist="Artist")
        merger.add_metadata_source("source1", metadata1, confidence=1.0)
        
        # Low confidence source
        metadata2 = AudioMetadata(
            title="Test",
            artist="Artist",
            album="Should Not Be Used",
            year=2020
        )
        merger.add_metadata_source("source2", metadata2, confidence=0.3)  # Below 0.5 threshold
        
        result = merger.merge_metadata()
        
        # Should not use fields from low confidence source
        assert result.album is None
        assert result.year is None
    
    def test_merge_metadata_cover_art_priority(self):
        """Test that cover art is taken from first available source."""
        merger = MetadataMerger()
        
        metadata1 = AudioMetadata(title="Test", artist="Artist")
        merger.add_metadata_source("source1", metadata1)
        
        metadata2 = AudioMetadata(
            title="Test",
            artist="Artist",
            cover_art_data=b"image data",
            cover_art_url="https://example.com/cover.jpg"
        )
        merger.add_metadata_source("source2", metadata2)
        
        result = merger.merge_metadata()
        
        assert result.cover_art_data == b"image data"
        assert result.cover_art_url == "https://example.com/cover.jpg"
    
    def test_get_metadata_summary(self):
        """Test get_metadata_summary method."""
        merger = MetadataMerger()
        metadata = AudioMetadata(title="Test", artist="Artist", year=2020)
        merger.add_metadata_source("source1", metadata)
        merger.merge_metadata()
        
        summary = merger.get_metadata_summary()
        
        assert summary["total_sources"] == 1
        assert len(summary["sources"]) == 1
        assert summary["sources"][0]["name"] == "source1"
        assert summary["final_metadata"] is not None
        assert summary["final_metadata"]["title"] == "Test"
    
    def test_get_metadata_summary_no_final_metadata(self):
        """Test get_metadata_summary without merged metadata."""
        merger = MetadataMerger()
        metadata = AudioMetadata(title="Test", artist="Artist")
        merger.add_metadata_source("source1", metadata)
        
        summary = merger.get_metadata_summary()
        
        assert summary["total_sources"] == 1
        assert summary["final_metadata"] is None
    
    @patch('builtins.print')
    def test_display_metadata_sources(self, mock_print):
        """Test display_metadata_sources method."""
        merger = MetadataMerger()
        metadata = AudioMetadata(title="Test", artist="Artist", year=2020)
        merger.add_metadata_source("source1", metadata)
        
        merger.display_metadata_sources()
        
        assert mock_print.called
        # Check that source information is printed
        call_args = str(mock_print.call_args_list)
        assert "source1" in call_args or "Test" in call_args
    
    @patch('builtins.print')
    def test_display_metadata_sources_empty(self, mock_print):
        """Test display_metadata_sources with no sources."""
        merger = MetadataMerger()
        
        merger.display_metadata_sources()
        
        mock_print.assert_called_with("No metadata sources available.")
    
    def test_set_final_metadata(self):
        """Test set_final_metadata method."""
        merger = MetadataMerger()
        metadata = AudioMetadata(title="Test", artist="Artist")
        
        merger.set_final_metadata(metadata)
        
        assert merger.final_metadata == metadata
    
    @patch('mutagen.File')
    def test_apply_metadata_to_file_success(self, mock_mutagen_file, temp_audio_file):
        """Test applying metadata to file successfully."""
        merger = MetadataMerger()
        metadata = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2020
        )
        merger.set_final_metadata(metadata)
        
        # Mock mutagen file
        mock_file = MagicMock()
        mock_mutagen_file.return_value = mock_file
        mock_file.tags = {}
        
        result = merger.apply_metadata_to_file(temp_audio_file, quiet=True)
        
        assert result is True
        mock_file.save.assert_called_once()
    
    def test_apply_metadata_to_file_no_metadata(self, temp_audio_file):
        """Test applying metadata when no final metadata is set."""
        merger = MetadataMerger()
        
        result = merger.apply_metadata_to_file(temp_audio_file)
        
        assert result is False
    
    @patch('mutagen.File')
    def test_apply_metadata_to_file_import_error(self, mock_mutagen_file, temp_audio_file):
        """Test applying metadata when mutagen is not available."""
        merger = MetadataMerger()
        metadata = AudioMetadata(title="Test", artist="Artist")
        merger.set_final_metadata(metadata)
        
        # Simulate ImportError
        mock_mutagen_file.side_effect = ImportError("No module named 'mutagen'")
        
        result = merger.apply_metadata_to_file(temp_audio_file)
        
        assert result is False

