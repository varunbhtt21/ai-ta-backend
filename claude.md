# AI-TA Backend Project

## Project Overview
This is the backend service for the AI Teaching Assistant (AI-TA) application, built with FastAPI and MongoDB. The project follows industry-standard patterns with a focus on architectural consistency and maintainable code structure.

## Tech Stack
- **Framework**: FastAPI
- **Database**: MongoDB with migration support
- **Package Management**: UV (for virtual environment and dependencies)
- **Configuration Management**: pyproject.toml
- **Environment Management**: .env files for different environments

## Project Structure
```
ai-ta-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models/          # All data models in one location
│   ├── services/        # Business logic layer (Service Layer Pattern)
│   ├── routers/         # API route handlers
│   ├── database/        # Database connection and utilities
│   ├── migrations/      # MongoDB migration scripts
│   ├── core/            # Core configurations and dependencies
│   └── utils/           # Utility functions
├── tests/               # Test scripts and test cases
├── .env.example         # Environment template
├── .env.dev             # Development environment variables
├── .env.prod            # Production environment variables
├── pyproject.toml       # Project configuration and dependencies
├── requirements.txt     # Generated from pyproject.toml
└── README.md
```

## Development Guidelines

### Architecture Principles
- **Service Layer Pattern**: Create dedicated service classes for business logic
- **Single Responsibility**: Each service handles specific domain logic
- **Architectural Consistency Over Feature Implementation**: Maintain consistent patterns even during rapid development
- **Centralized Models**: All data models in one location (`app/models/`)

### Environment Setup
- Use UV for virtual environment management
- Maintain separate virtual environment for backend
- Install packages using UV: `uv add package-name`
- Environment variables accessed from `.env` files

### Database Management
- **MongoDB** as primary database
- **Migration-based approach**: All schema changes through migration files
- Migration files location: `app/migrations/`
- Run migrations before deploying changes

### Environment Configuration
- `.env.example`: Template with all required environment variables
- `.env.dev`: Development environment configuration
- `.env.prod`: Production environment configuration
- All environment values accessed through configuration management

### Error Handling & Debugging Process
1. **Root Cause Analysis (RCA)**: Identify the underlying issue
2. **Fix Implementation**: Apply the solution
3. **Test Script Creation**: Create test script to verify fix
4. **Iterative Testing**: Test → Fix → Test cycle until resolution
5. **Cleanup**: Delete test scripts after successful resolution

### Code Organization Standards
- Keep files in appropriate directories
- Follow FastAPI best practices for routing
- Implement proper dependency injection
- Use Pydantic models for request/response validation
- Maintain clear separation between layers

### Testing Strategy
- All test scripts in `tests/` folder
- Unit tests for services
- Integration tests for API endpoints
- Database tests with test database
- Remove temporary test scripts after issue resolution

### Dependencies Management
- Use `pyproject.toml` for project configuration
- Pin dependency versions for production
- Regular dependency updates with testing

## Development Workflow
1. Set up virtual environment with UV
2. Configure environment variables
3. Run database migrations
4. Implement features following Service Layer pattern
5. Write tests for new functionality
6. Ensure architectural consistency
7. Document changes appropriately

## Quality Standards
- Code reviews for architectural consistency
- Proper error handling and logging
- Performance considerations for database queries
- Security best practices for API endpoints
- Documentation for complex business logic

## Notes
- Frontend code is separate (`ai-ta-frontend/` - currently blank)
- Focus exclusively on backend development
- Maintain clean separation between backend and frontend concerns
- Follow MongoDB best practices for document design