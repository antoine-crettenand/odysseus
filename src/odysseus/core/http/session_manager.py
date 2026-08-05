"""
Session manager for HTTP requests.
"""

import requests
from typing import Optional, Dict
from .network_agent import NetworkAgent


class SessionManager:
    """Manages HTTP sessions for different services."""

    def __init__(self, network_agent: Optional[NetworkAgent] = None):
        """
        Initialize session manager.

        Args:
            network_agent: Optional NetworkAgent instance
        """
        self.network_agent = network_agent
        self._sessions: Dict[str, requests.Session] = {}
        self._session_headers: Dict[str, Dict[str, str]] = {}

    def register_headers(self, name: str, headers: Dict[str, str]) -> None:
        """Persist provider headers so refreshed sessions keep auth and identity."""
        previous_headers = self._session_headers.get(name, {})
        self._session_headers[name] = dict(headers)
        if name in self._sessions:
            for key in previous_headers.keys() - headers.keys():
                self._sessions[name].headers.pop(key, None)
            self._sessions[name].headers.update(headers)

    def get_session(self, name: str = "default") -> requests.Session:
        """
        Get or create a session for the given name.

        Args:
            name: Session name identifier

        Returns:
            requests.Session instance
        """
        if name not in self._sessions:
            session = requests.Session()

            # Set default headers from network agent if available
            if self.network_agent:
                headers = self.network_agent.get_current_headers()
                session.headers.update(headers)

            # Provider headers deliberately take precedence over generic network
            # strategies. This preserves required User-Agent and Authorization
            # values after a connection-triggered session refresh.
            session.headers.update(self._session_headers.get(name, {}))

            self._sessions[name] = session

        return self._sessions[name]

    def refresh_session(self, name: str = "default") -> requests.Session:
        """
        Refresh a session (close and recreate).

        Args:
            name: Session name identifier

        Returns:
            New requests.Session instance
        """
        if name in self._sessions:
            self._sessions[name].close()
            del self._sessions[name]

        return self.get_session(name)
