"""
Tests for metadata service.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.services.metadata_service import MetadataService
from odysseus.models.song import AudioMetadata
from odysseus.models.releases import ReleaseInfo, Track


class TestMetadataService:
    """Tests for MetadataService class."""
    
    def test_metadata_service_initialization(self):
        """Test MetadataService initialization."""
        service = MetadataService()
        
        assert service.merger is not None
    
    def test_add_metadata_source(self):
        """Test add_metadata_source method."""
        service = MetadataService()
        metadata = AudioMetadata(title="Test", artist="Artist")
        
        service.add_metadata_source("source1", metadata, confidence=0.9)
        
        sources = service.get_metadata_sources()
        assert len(sources) == 1
        assert sources[0]['name'] == "source1"
        assert sources[0]['confidence'] == 0.9
    
    def test_merge_metadata(self):
        """Test merge_metadata method."""
        service = MetadataService()
        metadata1 = AudioMetadata(title="Test", artist="Artist")
        metadata2 = AudioMetadata(title="Test", artist="Artist", album="Album")
        
        service.add_metadata_source("source1", metadata1)
        service.add_metadata_source("source2", metadata2)
        
        merged = service.merge_metadata()
        
        assert merged.title == "Test"
        assert merged.artist == "Artist"
        assert merged.album == "Album"
    
    def test_get_metadata_sources(self):
        """Test get_metadata_sources method."""
        service = MetadataService()
        metadata = AudioMetadata(title="Test", artist="Artist")
        
        service.add_metadata_source("source1", metadata)
        
        sources = service.get_metadata_sources()
        assert len(sources) == 1
        assert sources[0]['name'] == "source1"
        assert 'metadata' in sources[0]
    
    @patch('mutagen.File')
    def test_apply_metadata_to_file(self, mock_mutagen_file, temp_audio_file):
        """Test apply_metadata_to_file method."""
        service = MetadataService()
        metadata = AudioMetadata(title="Test", artist="Artist")
        service.merger.set_final_metadata(metadata)
        
        mock_file = MagicMock()
        mock_mutagen_file.return_value = mock_file
        mock_file.tags = {}
        
        result = service.apply_metadata_to_file(str(temp_audio_file), quiet=True)
        
        assert result is True
    
    def test_set_final_metadata(self):
        """Test set_final_metadata method."""
        service = MetadataService()
        metadata = AudioMetadata(title="Test", artist="Artist")
        
        service.set_final_metadata(metadata)
        
        assert service.merger.final_metadata == metadata
    
    @patch('requests.get')
    def test_fetch_cover_art_success(self, mock_get):
        """Test fetch_cover_art with successful response."""
        service = MetadataService()
        
        # Mock cover art archive response
        mock_archive_response = MagicMock()
        mock_archive_response.status_code = 200
        mock_archive_response.json.return_value = {
            'images': [
                {
                    'front': True,
                    'image': 'https://example.com/cover.jpg'
                }
            ]
        }
        
        # Mock image response
        mock_image_response = MagicMock()
        mock_image_response.status_code = 200
        mock_image_response.content = b'fake image data'
        
        mock_get.side_effect = [mock_archive_response, mock_image_response]
        
        cover_art = service.fetch_cover_art("test-mbid-123")
        
        assert cover_art == b'fake image data'
    
    @patch('requests.get')
    def test_fetch_cover_art_no_front_cover(self, mock_get):
        """Test fetch_cover_art when no front cover available."""
        service = MetadataService()
        
        mock_archive_response = MagicMock()
        mock_archive_response.status_code = 200
        mock_archive_response.json.return_value = {
            'images': [
                {
                    'front': False,
                    'image': 'https://example.com/back.jpg'
                }
            ]
        }
        
        mock_image_response = MagicMock()
        mock_image_response.status_code = 200
        mock_image_response.content = b'fake image data'
        
        mock_get.side_effect = [mock_archive_response, mock_image_response]
        
        cover_art = service.fetch_cover_art("test-mbid-123")
        
        # Should use first image if no front cover
        assert cover_art == b'fake image data'
    
    @patch('requests.get')
    def test_fetch_cover_art_failure(self, mock_get):
        """Test fetch_cover_art when request fails."""
        service = MetadataService()
        
        mock_get.side_effect = Exception("Network error")
        
        cover_art = service.fetch_cover_art("test-mbid-123")
        
        assert cover_art is None
    
    @patch('odysseus.services.metadata_service.MetadataService.fetch_cover_art')
    @patch('mutagen.File')
    def test_apply_metadata_with_cover_art(self, mock_mutagen_file, mock_fetch_cover, temp_audio_file):
        """Test apply_metadata_with_cover_art method."""
        service = MetadataService()
        
        track = Track(position=1, title="Track 1", artist="Artist")
        release_info = ReleaseInfo(
            title="Album",
            artist="Artist",
            release_date="2020-01-01",
            genre="Rock",
            mbid="test-mbid-123",
            tracks=[track]
        )
        
        mock_fetch_cover.return_value = b'fake cover art'
        mock_file = MagicMock()
        mock_mutagen_file.return_value = mock_file
        mock_file.tags = {}
        
        service.apply_metadata_with_cover_art(temp_audio_file, track, release_info)
        
        assert mock_fetch_cover.called
        assert service.merger.final_metadata is not None
        assert service.merger.final_metadata.cover_art_data == b'fake cover art'

