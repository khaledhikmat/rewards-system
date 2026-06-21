"""
HTTP handler implementation using FastAPI.
"""
import logging
import secrets
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Depends, status, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature

from ...services.database.typex import IDatabaseService, TeamModel, StatsModel
from ..telegram.typex import ITelegramHandler

logger = logging.getLogger(__name__)


class HttpHandler:
    """
    HTTP handler implementation using FastAPI.
    Implements the IHttpHandler protocol.
    """

    def __init__(
        self,
        db_service: IDatabaseService,
        telegram_handler: ITelegramHandler,
        api_key: str,
        admin_username: str,
        admin_password: str,
        templates_dir: str = "templates",
        lifespan=None
    ):
        """
        Initialize the HTTP handler.

        Args:
            db_service: Database service instance
            telegram_handler: Telegram handler instance
            api_key: API key for authentication
            admin_username: Admin username for dashboard
            admin_password: Admin password for dashboard
            templates_dir: Directory containing templates
            lifespan: Optional lifespan context manager for FastAPI
        """
        self.db_service = db_service
        self.telegram_handler = telegram_handler
        self.api_key = api_key
        self.admin_username = admin_username
        self.admin_password = admin_password

        # Session management
        self.secret_key = secrets.token_urlsafe(32)
        self.serializer = URLSafeTimedSerializer(self.secret_key)

        # Create FastAPI app with optional lifespan
        self.app = FastAPI(
            title="Reward Tracker API",
            description="API for managing family reward tracking system",
            version="1.0.0",
            lifespan=lifespan
        )

        # Set up templates
        self.templates = Jinja2Templates(directory=templates_dir)

        # Register routes
        self._register_routes()

    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app

    async def initialize(self) -> None:
        """Initialize the HTTP handler."""
        logger.info("HTTP handler initialized")

    async def shutdown(self) -> None:
        """Cleanup when shutting down."""
        logger.info("HTTP handler shutdown")

    # ========================================================================
    # Authentication Helpers
    # ========================================================================

    def _create_session_token(self, username: str) -> str:
        """Create a signed session token."""
        return self.serializer.dumps(username, salt="session")

    def _verify_session_token(self, token: str) -> Optional[str]:
        """Verify session token and return username if valid."""
        try:
            # Token expires after 24 hours
            username = self.serializer.loads(token, salt="session", max_age=86400)
            return username
        except (BadSignature, Exception):
            return None

    def _get_current_user(self, request: Request) -> str:
        """Get current logged-in user from session cookie."""
        session_token = request.cookies.get("session")
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"}
            )

        username = self._verify_session_token(session_token)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"}
            )

        return username

    def _verify_api_key(self, request: Request) -> bool:
        """Verify API key from request headers."""
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != self.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key"
            )
        return True

    # ========================================================================
    # Route Registration
    # ========================================================================

    def _register_routes(self) -> None:
        """Register all routes."""

        # Health check endpoint
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy"}

        # Telegram webhook endpoint
        @self.app.post("/webhook/telegram")
        async def telegram_webhook(request: Request):
            """Handle Telegram webhook updates."""
            try:
                update_data = await request.json()
                await self.telegram_handler.handle_webhook(update_data)
                return {"ok": True}
            except Exception as e:
                logger.error(f"Error processing Telegram webhook: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process webhook"
                )

        # Team endpoints (API key required)
        @self.app.get("/api/teams", response_model=List[TeamModel])
        async def get_teams(request: Request, _: bool = Depends(self._verify_api_key)):
            """Get all teams."""
            try:
                teams = await self.db_service.get_all_teams()
                return teams
            except Exception as e:
                logger.error(f"Error getting teams: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve teams"
                )

        @self.app.get("/api/teams/{team_id}", response_model=TeamModel)
        async def get_team(
            team_id: int,
            request: Request,
            _: bool = Depends(self._verify_api_key)
        ):
            """Get a specific team by ID."""
            try:
                team = await self.db_service.get_team(team_id)
                if not team:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Team {team_id} not found"
                    )
                return team
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting team {team_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve team"
                )

        @self.app.post("/api/teams", status_code=status.HTTP_201_CREATED)
        async def create_team(
            team: TeamModel,
            request: Request,
            _: bool = Depends(self._verify_api_key)
        ):
            """Create a new team."""
            try:
                team_id = await self.db_service.create_team(team)
                return {"id": team_id, "message": "Team created successfully"}
            except Exception as e:
                logger.error(f"Error creating team: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create team: {str(e)}"
                )

        @self.app.put("/api/teams/{team_id}")
        async def update_team(
            team_id: int,
            team: TeamModel,
            request: Request,
            _: bool = Depends(self._verify_api_key)
        ):
            """Update an existing team."""
            try:
                # Check if team exists
                existing_team = await self.db_service.get_team(team_id)
                if not existing_team:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Team {team_id} not found"
                    )

                # Update the team
                await self.db_service.update_team(team_id, team)
                return {"message": "Team updated successfully"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error updating team {team_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update team: {str(e)}"
                )

        @self.app.delete("/api/teams/{team_id}")
        async def delete_team(
            team_id: int,
            request: Request,
            _: bool = Depends(self._verify_api_key)
        ):
            """Delete a team."""
            try:
                # Check if team exists
                existing_team = await self.db_service.get_team(team_id)
                if not existing_team:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Team {team_id} not found"
                    )

                # Delete the team
                await self.db_service.delete_team(team_id)
                return {"message": "Team deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error deleting team {team_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete team: {str(e)}"
                )

        # Stats endpoint (API key required)
        @self.app.get("/api/stats", response_model=StatsModel)
        async def get_stats(request: Request, _: bool = Depends(self._verify_api_key)):
            """Get system statistics."""
            try:
                stats = await self.db_service.get_stats()
                return stats
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve statistics"
                )

        # Login page
        @self.app.get("/login", response_class=HTMLResponse)
        async def login_page(request: Request):
            """Serve the login page."""
            return self.templates.TemplateResponse(
                "login.html",
                {"request": request, "error": None}
            )

        # Login form handler
        @self.app.post("/login")
        async def login(
            request: Request,
            username: str = Form(...),
            password: str = Form(...)
        ):
            """Handle login form submission."""
            # Verify credentials
            if username == self.admin_username and password == self.admin_password:
                # Create session token
                token = self._create_session_token(username)

                # Redirect to dashboard with session cookie
                response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
                response.set_cookie(
                    key="session",
                    value=token,
                    httponly=True,
                    max_age=86400,  # 24 hours
                    samesite="lax"
                )
                return response
            else:
                # Invalid credentials
                return self.templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "error": "Invalid username or password"
                    },
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

        # Logout
        @self.app.get("/logout")
        async def logout():
            """Logout and clear session."""
            response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
            response.delete_cookie("session")
            return response

        # Stats cards endpoint for HTMX refresh
        @self.app.get("/api/stats-cards", response_class=HTMLResponse)
        async def stats_cards(
            request: Request,
            _: str = Depends(self._get_current_user)
        ):
            """Return just the stats cards HTML for HTMX refresh."""
            try:
                stats = await self.db_service.get_stats()

                stats_html = f"""
            <div class="stat-card teams">
                <h3>Total Teams</h3>
                <div class="value">{stats.total_teams}</div>
            </div>

            <div class="stat-card recipients">
                <h3>Total Recipients</h3>
                <div class="value">{stats.total_recipients}</div>
            </div>

            <div class="stat-card evaluators">
                <h3>Total Evaluators</h3>
                <div class="value">{stats.total_evaluators}</div>
            </div>

            <div class="stat-card total">
                <h3>Total Evaluations</h3>
                <div class="value">{stats.total_evaluations}</div>
            </div>

            <div class="stat-card queued">
                <h3>Queued</h3>
                <div class="value">{stats.queued_evaluations}</div>
            </div>

            <div class="stat-card processing">
                <h3>Processing</h3>
                <div class="value">{stats.processing_evaluations}</div>
            </div>

            <div class="stat-card completed">
                <h3>Completed</h3>
                <div class="value">{stats.completed_evaluations}</div>
            </div>

            <div class="stat-card failed">
                <h3>Failed</h3>
                <div class="value">{stats.failed_evaluations}</div>
            </div>
                """
                return HTMLResponse(content=stats_html)

            except Exception as e:
                logger.error(f"Error loading stats: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to load statistics"
                )

        # Admin dashboard (requires session auth)
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(
            request: Request,
            _: str = Depends(self._get_current_user)
        ):
            """Serve the admin dashboard."""
            try:
                stats = await self.db_service.get_stats()
                teams = await self.db_service.get_all_teams()

                return self.templates.TemplateResponse(
                    "dashboard.html",
                    {
                        "request": request,
                        "stats": stats,
                        "teams": teams
                    }
                )
            except Exception as e:
                logger.error(f"Error loading dashboard: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to load dashboard"
                )
