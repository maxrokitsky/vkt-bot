# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VK Teams Bot providing tools for messenger convenience and integration with other systems. This is a monorepo containing the main bot application, framework packages, and plugins.

**Language:** Python 3.13+
**Package Manager:** uv

## Repository Structure

This is a **uv workspace** with three main components:

### Main Application: `vkt-bot`
- Location: `src/vkt_bot/`
- The primary bot application integrating all components

### Framework Packages: `packages/`
- **vkt-dispatcher**: Framework managing bot lifecycle and event handlers
  - Core dispatcher implementation with middleware support
  - Handler base classes for different event types
  - Filter system for event routing
- **vkteams-client**: Async client for VK Teams Bot API
  - Low-level API wrapper with aiohttp
  - Pydantic models for API types

### Plugins: `plugins/`
- **vkt-gitlab**: GitLab integration plugin
  - Pipeline notifications
  - Uses entry points (`vkt_bot.plugins` group) for auto-discovery
  - Install method called during bot startup

## Development Commands

### Running the Bot
```bash
uv run bot           # Start the bot polling for events
make bot             # Alternative using Makefile
```

### Running the Web Server
```bash
uv run server        # Start FastAPI web server on 0.0.0.0:8000
make server          # Alternative using Makefile
```

### Interactive Shell
```bash
uv run shell         # IPython shell with database session loaded
```

### Database Migrations
```bash
alembic upgrade head           # Apply all pending migrations
alembic revision --autogenerate -m "message"  # Generate migration
make migrate                   # Apply migrations via Makefile
```

### Code Quality
```bash
ruff check           # Lint code
ruff check --fix     # Auto-fix linting issues
ruff format          # Format code
```

### Dependencies
```bash
uv sync              # Install/sync all dependencies
uv add <package>     # Add dependency to main project
uv add --dev <package>  # Add dev dependency
```

### Docker
```bash
docker-compose up postgres-db  # Start PostgreSQL database
```

## Architecture

### Event-Driven Handler System

The bot uses an event-driven architecture with the following flow:

1. **Polling**: `Dispatcher.start_polling()` polls VK Teams API for events
2. **Event Routing**: `Dispatcher.trigger(event)` applies middlewares and checks handlers
3. **Handler Execution**: Matching handlers run concurrently via `asyncio.TaskGroup`

**Handler Registration:**
- Handlers are auto-registered by importing their modules
- Core handlers in `src/vkt_bot/core/handlers/` (chats, roles, help)
- Plugin handlers registered via plugin `install()` method

**Handler Types:**
- `MessageHandler`: New messages
- `CommandHandler`: Commands (text starting with `/`)
- `BotButtonCommandHandler`: Callback queries from inline buttons
- `NewChatMembersHandler`, `LeftChatMembersHandler`: Chat member events
- `EditedMessageHandler`, `DeletedMessageHandler`: Message modifications

**Filters:**
- Defined in `vkt_dispatcher.filters`
- Composable with `&` (and), `|` (or), `~` (not) operators
- Example: `Filter.command & Filter.private` for private commands only

### Plugin System

Plugins use Python entry points for auto-discovery:

1. Define entry point in plugin's `pyproject.toml`:
   ```toml
   [project.entry-points.'vkt_bot.plugins']
   plugin_name = "module_path"
   ```

2. Implement `install()` function in plugin module:
   ```python
   def install() -> None:
       from . import models  # Register SQLAlchemy models
       from . import handlers  # Register event handlers
       from . import api  # Optional: add FastAPI routes
   ```

3. Plugin loads automatically on bot startup via `importlib.metadata.entry_points`

### Database Layer

**ORM:** SQLAlchemy 2.0 (async)

**Pattern:** Repository pattern with three layers:
- **Models**: SQLAlchemy ORM models (`src/vkt_bot/core/models/`)
- **Repositories**: CRUD operations (`src/vkt_bot/core/repositories/`)
  - Inherit from `AsyncRepository[Model, PK, CreateSchema, UpdateSchema]`
  - Type-safe with generic types auto-inferred
- **Queries**: Reusable query logic (`src/vkt_bot/core/queries/`)
  - Implement `Query` protocol with `apply(stmt)` method
  - Composable via `repository.query(Query1(), Query2())`

**Session Management:**
- Bot handlers: Use dependency injection or create sessions manually
- Web API: Dependency injection via `get_session()` in `webapp/dependencies.py`

**Migrations:**
- Tool: Alembic
- Location: `src/vkt_bot/migrations/`
- Config: `pyproject.toml` under `[tool.alembic]`
- Post-write hooks: Auto-format migrations with ruff

### Web Application

**Framework:** FastAPI
**Location:** `src/vkt_bot/webapp/`

**Structure:**
- `app.py`: FastAPI app instance with all routers
- `api/`: API route modules
  - `auth.py`: JWT authentication (login, get current user)
  - `users.py`: User management CRUD (admin only)
  - `chats.py`: Chat viewing (admin only)
  - `roles.py`: Role management CRUD and members (admin only)
- `schemas/`: Pydantic schemas for request/response validation
- `dependencies.py`: Dependency injection (session, auth, admin check)
- `client/vkt-bot-dashboard/`: Frontend dashboard (separate directory)

**Authentication:**
- JWT-based with Bearer token
- Secret key required in `.env` (`SECRET_KEY`)
- Two-tier access: authenticated users and admin users
- Admin check via `is_superuser` flag on User model

**Key Dependencies:**
- `CurrentUser`: Annotated dependency for authenticated user
- `CurrentAdminUser`: Annotated dependency for admin user
- `SessionDep`: Annotated dependency for database session

**API Documentation:** Available at `/docs` (Swagger) and `/redoc`

### Configuration

Configuration via Pydantic Settings loaded from `.env`:

**Required:**
- `BOT_TOKEN`: VK Teams bot token
- `DB_URL`: PostgreSQL connection URL (DSN format)
- `LOGGING`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Optional:**
- `OWNER_ID`: Bot owner user ID
- `SECRET_KEY`: JWT secret for web API
- `PUBLIC_URL`: Public URL for webhooks
- `SENTRY_DSN`: Sentry error tracking
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT expiration (default: 8 days)
- `LOG_FILE`: Path to log file

### Logging

Structured logging with multiple loggers:
- `vkt_bot.main`: Main application logger
- `vkt_dispatcher`: Dispatcher framework
- `vkteams_client`: API client (events, send_message)
- Configured in `src/vkt_bot/loggers.py` and `src/vkt_bot/utils/log.py`

## Key Files

- [main.py](src/vkt_bot/main.py) - Entry points (`start_bot`, `start_server`, `shell`)
- [app.py](src/vkt_bot/app.py) - Global `bot` and `dispatcher` instances
- [config.py](src/vkt_bot/config.py) - Settings schema and validation
- [__init__.py](src/vkt_bot/__init__.py) - `setup()` function (logging, Sentry, plugin loading)
- [dispatcher.py](packages/vkt-dispatcher/src/vkt_dispatcher/dispatcher.py) - Core dispatcher logic
- [handlers.py](packages/vkt-dispatcher/src/vkt_dispatcher/handlers.py) - Handler base classes
- [client.py](packages/vkteams-client/src/vkteams_client/client.py) - VK Teams API client

## Development Workflow

1. **Adding a new handler:**
   - Create handler class inheriting from appropriate base (e.g., `CommandHandler`)
   - Register with `dispatcher.register_handler(MyHandler())`
   - Usually registered in `src/vkt_bot/core/handlers/` modules

2. **Adding a new plugin:**
   - Create plugin directory in `plugins/`
   - Add `pyproject.toml` with entry point
   - Implement `install()` function
   - Plugin auto-loads on next bot start

3. **Database changes:**
   - Modify model in `src/vkt_bot/core/models/` or plugin models
   - Generate migration: `alembic revision --autogenerate -m "description"`
   - Review and edit generated migration
   - Apply: `alembic upgrade head`

4. **Web API endpoints:**
   - Add route in `src/vkt_bot/webapp/api/`
   - Create schemas in `src/vkt_bot/webapp/schemas/`
   - Include router in `webapp/app.py`
   - Use `CurrentAdminUser` dependency for admin-only endpoints
   - Full documentation in [webapp/README.md](src/vkt_bot/webapp/README.md)

5. **Creating admin user:**
   - Use script: `uv run python -m vkt_bot.scripts.create_admin <username> <password> <email>`
   - First admin needed before using web API

## Testing

Test framework not currently configured (pytest in dev dependencies but no tests directory).

## Deployment

- **Docker:** `Dockerfile` and `docker-compose.yaml` provided
- **Services:** PostgreSQL database (RabbitMQ config commented out)
- Build uses uv with `--all-packages` flag for monorepo support
