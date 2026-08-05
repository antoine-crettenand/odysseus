"""
Polymorphic Network Agent Module
A network agent that adapts headers and connection strategies based on error patterns.
"""

import threading
import requests
from typing import Dict, List, Optional, Any
from urllib3.exceptions import ProtocolError


class HeaderStrategy:
    """Represents a header configuration strategy."""
    
    def __init__(self, name: str, headers: Dict[str, str]):
        self.name = name
        self.headers = headers
    
    def __repr__(self):
        return f"HeaderStrategy(name={self.name}, headers={self.headers})"


class NetworkAgent:
    """
    Polymorphic network agent that adapts headers based on connection errors.
    
    This agent maintains multiple header strategies and switches between them
    when specific error patterns are detected.
    """
    
    def __init__(self, base_user_agent: str, base_headers: Optional[Dict[str, str]] = None):
        """
        Initialize the network agent.
        
        Args:
            base_user_agent: Base user agent string
            base_headers: Base headers dictionary (optional)
        """
        self.base_user_agent = base_user_agent
        self.base_headers = base_headers or {}
        
        # Initialize header strategies
        self.strategies: List[HeaderStrategy] = []
        self.current_strategy_index = 0
        self._strategy_lock = threading.Lock()
        
        # Create default strategies
        self._initialize_strategies()
        
        # Track which errors triggered strategy changes
        self.error_history: List[Dict[str, Any]] = []
    
    def _initialize_strategies(self):
        """Initialize default header strategies."""
        # Strategy 0: Default with Connection: close
        self.strategies.append(HeaderStrategy(
            "default_close",
            {
                'User-Agent': self.base_user_agent,
                'Accept': 'application/json',
                'Connection': 'close'
            }
        ))
        
        # Strategy 1: Keep-Alive connection
        self.strategies.append(HeaderStrategy(
            "keep_alive",
            {
                'User-Agent': self.base_user_agent,
                'Accept': 'application/json',
                'Connection': 'keep-alive'
            }
        ))
        
        # Strategy 2: No Connection header (let requests handle it)
        self.strategies.append(HeaderStrategy(
            "no_connection_header",
            {
                'User-Agent': self.base_user_agent,
                'Accept': 'application/json'
            }
        ))
        
        # Strategy 3: Alternative User-Agent with close
        alternative_ua = self.base_user_agent.replace('/', ' (compatible; NetworkAgent/1.0) /')
        self.strategies.append(HeaderStrategy(
            "alt_user_agent_close",
            {
                'User-Agent': alternative_ua,
                'Accept': 'application/json',
                'Connection': 'close'
            }
        ))
        
        # Strategy 4: Minimal headers
        self.strategies.append(HeaderStrategy(
            "minimal",
            {
                'User-Agent': self.base_user_agent,
                'Accept': '*/*'
            }
        ))
    
    def get_current_headers(self) -> Dict[str, str]:
        """Get the current header strategy."""
        strategy = self.strategies[self.current_strategy_index]
        # Merge with base headers (base headers take precedence)
        headers = {**strategy.headers, **self.base_headers}
        return headers
    
    def get_current_strategy_name(self) -> str:
        """Get the name of the current strategy."""
        return self.strategies[self.current_strategy_index].name
    
    def _is_protocol_error_invalid_argument(self, error: Exception) -> bool:
        """
        Check if the error is a ProtocolError with OSError(22, 'Invalid argument').
        
        This handles nested exceptions like:
        ConnectionError -> ProtocolError('Connection aborted.', OSError(22, 'Invalid argument'))
        
        Args:
            error: The exception to check
            
        Returns:
            True if it matches the pattern, False otherwise
        """
        error_str = str(error).lower()
        error_repr = repr(error).lower()
        
        # Check for ProtocolError in string representation
        has_protocol_error = 'protocolerror' in error_str or 'protocolerror' in error_repr
        
        # Check for "Connection aborted"
        has_connection_aborted = (
            'connection aborted' in error_str or 
            'connection aborted' in error_repr or
            'connection aborted' in str(error.args).lower()
        )
        
        # Check for Invalid argument or OSError(22)
        has_invalid_arg = (
            'invalid argument' in error_str or 
            'invalid argument' in error_repr or
            'oserror(22' in error_str or
            'oserror(22' in error_repr
        )
        
        # Direct check: ProtocolError with Connection aborted and Invalid argument
        if has_protocol_error and has_connection_aborted and has_invalid_arg:
            return True
        
        # Check if error is a ProtocolError instance
        if isinstance(error, ProtocolError):
            if has_connection_aborted:
                # Check args for OSError(22)
                if hasattr(error, 'args') and error.args:
                    for arg in error.args:
                        if isinstance(arg, OSError) and arg.errno == 22:
                            return True
                        if isinstance(arg, str) and 'invalid argument' in arg.lower():
                            return True
        
        # Check the underlying exception chain (__cause__)
        current_error: BaseException = error
        depth = 0
        max_depth = 5  # Prevent infinite loops
        
        while current_error and depth < max_depth:
            # Check if current error is ProtocolError
            if isinstance(current_error, ProtocolError):
                if hasattr(current_error, 'args') and current_error.args:
                    for arg in current_error.args:
                        if isinstance(arg, OSError) and arg.errno == 22:
                            return True
                        if isinstance(arg, str) and 'invalid argument' in str(arg).lower():
                            if 'connection aborted' in str(current_error).lower():
                                return True
            
            # Check if current error has OSError(22) in args
            if hasattr(current_error, 'args') and current_error.args:
                for arg in current_error.args:
                    if isinstance(arg, OSError) and arg.errno == 22:
                        # Check if parent mentions ProtocolError or Connection aborted
                        parent_str = str(error).lower()
                        if 'protocolerror' in parent_str or 'connection aborted' in parent_str:
                            return True
            
            # Move to next level in exception chain
            if hasattr(current_error, '__cause__') and current_error.__cause__:
                current_error = current_error.__cause__
            elif hasattr(current_error, '__context__') and current_error.__context__:
                current_error = current_error.__context__
            else:
                break
            depth += 1
        
        return False
    
    def should_switch_strategy(self, error: Exception) -> bool:
        """
        Determine if we should switch header strategy based on the error.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if strategy should be switched, False otherwise
        """
        return self._is_protocol_error_invalid_argument(error)
    
    def switch_to_next_strategy(self, error: Optional[Exception] = None) -> bool:
        """
        Switch to the next header strategy.
        
        Args:
            error: Optional error that triggered the switch
            
        Returns:
            True if switched to a new strategy, False if all strategies exhausted
        """
        with self._strategy_lock:
            if error:
                self.error_history.append({
                    'error_type': type(error).__name__,
                    'error_message': str(error),
                    'strategy_before': self.get_current_strategy_name(),
                    'attempt': len(self.error_history) + 1
                })

            if self.current_strategy_index < len(self.strategies) - 1:
                self.current_strategy_index += 1
                return True

            # Reset to first strategy if we've tried all
            self.current_strategy_index = 0
            return False
    
    def reset_to_default(self):
        """Reset to the default strategy."""
        with self._strategy_lock:
            self.current_strategy_index = 0
    
    def add_strategy(self, name: str, headers: Dict[str, str]):
        """
        Add a custom header strategy.
        
        Args:
            name: Name of the strategy
            headers: Headers dictionary for this strategy
        """
        with self._strategy_lock:
            self.strategies.append(HeaderStrategy(name, headers))
    
    def update_session_headers(self, session: requests.Session):
        """
        Update a requests Session with the current header strategy.
        
        Args:
            session: The requests Session to update
        """
        current_headers = self.get_current_headers()
        session.headers.update(current_headers)
    
    def create_fresh_session(self) -> requests.Session:
        """
        Create a new requests Session with the current header strategy.
        
        Returns:
            A new requests.Session configured with current headers
        """
        session = requests.Session()
        self.update_session_headers(session)
        return session

