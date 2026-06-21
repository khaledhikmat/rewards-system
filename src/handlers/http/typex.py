"""
HTTP handler type definitions and protocols.
"""
from typing import Protocol
from fastapi import FastAPI


class IHttpHandler(Protocol):
    """Protocol defining the HTTP handler interface."""

    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.

        Returns:
            The FastAPI application
        """
        ...

    async def initialize(self) -> None:
        """Initialize the HTTP handler."""
        ...

    async def shutdown(self) -> None:
        """Cleanup when shutting down."""
        ...
