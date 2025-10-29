#!/usr/bin/env python3
"""
API Configuration Module
Configuration for external music metadata APIs.
"""

import os
from typing import Dict, Optional


class APIConfig:
    """Configuration for external music metadata APIs."""
    
    def __init__(self):
        self.config = {
            'discogs': {
                'token': os.getenv('DISCOGS_TOKEN'),
                'description': 'Discogs API token (optional but recommended for higher rate limits)',
                'signup_url': 'https://www.discogs.com/settings/developers',
                'rate_limit': '60 requests per minute (with token), 25 requests per minute (without)'
            },
            'lastfm': {
                'api_key': os.getenv('LASTFM_API_KEY'),
                'description': 'Last.fm API key (required)',
                'signup_url': 'https://www.last.fm/api/account/create',
                'rate_limit': '5 requests per second'
            },
            'spotify': {
                'client_id': os.getenv('SPOTIFY_CLIENT_ID'),
                'client_secret': os.getenv('SPOTIFY_CLIENT_SECRET'),
                'description': 'Spotify Web API credentials (required)',
                'signup_url': 'https://developer.spotify.com/dashboard/applications',
                'rate_limit': '10 requests per second'
            },
            'genius': {
                'access_token': os.getenv('GENIUS_ACCESS_TOKEN'),
                'description': 'Genius API access token (required)',
                'signup_url': 'https://genius.com/api-clients',
                'rate_limit': '5 requests per second'
            }
        }
    
    def get_config(self, service: str) -> Optional[Dict[str, str]]:
        """Get configuration for a specific service."""
        return self.config.get(service)
    
    def is_configured(self, service: str) -> bool:
        """Check if a service is properly configured."""
        config = self.get_config(service)
        if not config:
            return False
        
        if service == 'discogs':
            # Discogs token is optional
            return True
        elif service == 'lastfm':
            return config.get('api_key') is not None
        elif service == 'spotify':
            return (config.get('client_id') is not None and 
                   config.get('client_secret') is not None)
        elif service == 'genius':
            return config.get('access_token') is not None
        
        return False
    
    def get_configured_services(self) -> list:
        """Get list of properly configured services."""
        return [service for service in self.config.keys() if self.is_configured(service)]
    
    def print_setup_instructions(self):
        """Print setup instructions for all services."""
        print("=== Music Metadata API Setup Instructions ===\n")
        
        for service, config in self.config.items():
            print(f"🔧 {service.upper()}")
            print(f"   Description: {config['description']}")
            print(f"   Sign up: {config['signup_url']}")
            print(f"   Rate limit: {config['rate_limit']}")
            
            if service == 'discogs':
                print(f"   Environment variable: DISCOGS_TOKEN (optional)")
            elif service == 'lastfm':
                print(f"   Environment variable: LASTFM_API_KEY")
            elif service == 'spotify':
                print(f"   Environment variables: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET")
            elif service == 'genius':
                print(f"   Environment variable: GENIUS_ACCESS_TOKEN")
            
            print(f"   Configured: {'✅ Yes' if self.is_configured(service) else '❌ No'}")
            print()
        
        print("To set environment variables:")
        print("  export DISCOGS_TOKEN='your_token_here'")
        print("  export LASTFM_API_KEY='your_api_key_here'")
        print("  export SPOTIFY_CLIENT_ID='your_client_id_here'")
        print("  export SPOTIFY_CLIENT_SECRET='your_client_secret_here'")
        print("  export GENIUS_ACCESS_TOKEN='your_access_token_here'")
        print()
        print("Or create a .env file in your project root with:")
        print("  DISCOGS_TOKEN=your_token_here")
        print("  LASTFM_API_KEY=your_api_key_here")
        print("  SPOTIFY_CLIENT_ID=your_client_id_here")
        print("  SPOTIFY_CLIENT_SECRET=your_client_secret_here")
        print("  GENIUS_ACCESS_TOKEN=your_access_token_here")


def create_metadata_merger_with_apis() -> 'MetadataMerger':
    """Create a MetadataMerger instance with all configured APIs."""
    from metadata_merger import MetadataMerger
    
    config = APIConfig()
    
    return MetadataMerger(
        discogs_token=config.get_config('discogs')['token'],
        lastfm_api_key=config.get_config('lastfm')['api_key'],
        spotify_client_id=config.get_config('spotify')['client_id'],
        spotify_client_secret=config.get_config('spotify')['client_secret'],
        genius_access_token=config.get_config('genius')['access_token']
    )


if __name__ == "__main__":
    config = APIConfig()
    config.print_setup_instructions()
    
    print("=== Currently Configured Services ===")
    configured = config.get_configured_services()
    if configured:
        for service in configured:
            print(f"✅ {service}")
    else:
        print("❌ No services configured")
        print("\nPlease set up at least one API to use the enhanced metadata features.")
