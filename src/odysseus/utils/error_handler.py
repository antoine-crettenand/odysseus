"""
Error handling utilities and decorators.
"""
from functools import wraps
from typing import Callable, TypeVar, Optional, Any
from ..core.exceptions import OdysseusError

T = TypeVar('T')


def handle_errors(
    error_message: str = "An error occurred",
    reraise: bool = False,
    display_manager: Optional[Any] = None,
    default_return: Optional[Any] = None
):
    """
    Decorator to handle errors consistently.
    
    Args:
        error_message: Default error message if exception doesn't have one
        reraise: Whether to re-raise the exception after handling
        display_manager: Optional display manager to show errors
        default_return: Value to return on error (if not reraise)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except OdysseusError as e:
                if display_manager and hasattr(display_manager, 'console'):
                    display_manager.console.print(f"[bold red]✗[/bold red] {e.message}")
                if reraise:
                    raise
                return default_return
            except Exception as e:
                error_msg = error_message
                if hasattr(e, '__str__'):
                    error_msg = f"{error_message}: {e}"
                
                if display_manager and hasattr(display_manager, 'console'):
                    display_manager.console.print(f"[bold red]✗[/bold red] {error_msg}")
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def safe_execute(
    func: Callable[..., T],
    error_message: str = "Operation failed",
    default_return: Optional[Any] = None,
    display_manager: Optional[Any] = None
) -> Optional[T]:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        error_message: Error message to display
        default_return: Value to return on error
        display_manager: Optional display manager to show errors
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func()
    except OdysseusError as e:
        if display_manager and hasattr(display_manager, 'console'):
            display_manager.console.print(f"[bold red]✗[/bold red] {e.message}")
        return default_return
    except Exception as e:
        error_msg = f"{error_message}: {e}" if str(e) else error_message
        if display_manager and hasattr(display_manager, 'console'):
            display_manager.console.print(f"[bold red]✗[/bold red] {error_msg}")
        return default_return

