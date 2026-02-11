# AGENTS.md

This guide is for agentic coding assistants working in the MX Fantasy League repository.

## Build/Test/Lint Commands

### Running the Application
```bash
# Development mode (Flask dev server)
python app.py
# or
python main.py

# Startup scripts
./start.sh          # Linux/Mac
start.bat           # Windows

# Production mode
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 main:app

# Docker
docker-compose up -d
docker-compose logs -f
```

### Testing
No formal test framework (pytest/unittest). Test files are standalone scripts:
```bash
# Run individual test files
python test_db.py
python test_import.py
python quick_test.py
python <any_test_file>.py
```

### Database Migrations
Uses Alembic for database migrations (migrations/ directory):
```bash
# Create migration (if using Flask-Migrate)
# Check migrations/alembic.ini and env.py for setup
flask db migrate -m "description"
flask db upgrade
```

## Code Style Guidelines

### Imports
- Order: Standard library → Third-party → Local imports
- Use `from __future__ import annotations` in route files for forward references
- Import models from `models.py`: `from models import db, User, Competition, Rider`
- Group related imports, avoid wildcard imports
- Add `# type: ignore` or `# noqa: <code>` when suppressing warnings

### Formatting
- Use 4 spaces for indentation (not tabs)
- Keep lines under 100-120 characters when practical
- Blank lines between functions and classes (2 lines for classes, 1 for functions)
- Add docstrings for non-trivial functions

### Types
- Python 3.11 target
- Use type hints where helpful: `def is_admin_user() -> bool:`
- `from __future__ import annotations` for forward references in type hints
- SQLAlchemy models use db.Column types: db.String, db.Integer, db.Boolean, db.DateTime, db.Text

### Naming Conventions
- **Classes**: PascalCase - `User`, `Competition`, `SeasonTeam`
- **Functions/Variables**: snake_case - `get_today()`, `is_admin_user`, `rider_id`
- **Constants**: UPPER_SNAKE_CASE - `UPLOAD_FOLDER`, `ALLOWED_EXTENSIONS`, `MAX_CONTENT_LENGTH`
- **Database tables**: lowercase plural - `__tablename__ = "users"`
- **Blueprints**: lowercase - `bp = Blueprint('api', ...)`
- **Route parameters**: descriptive - `<int:rider_id>`, `<int:competition_id>`

### Routes & Blueprints
- Organize routes in `app/routes/` using Flask Blueprints
- Use specific decorators: `@bp.get()`, `@bp.post()`, `@bp.route(methods=[])`
- Prefix routes appropriately: `/api`, `/admin`, etc.
- RESTful patterns for API endpoints
```python
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.get('/riders')
def get_riders():
    return jsonify([...])

@bp.post('/riders')
def create_rider():
    data = request.get_json()
    # ...
    return jsonify({...}), 201
```

### Error Handling
- Wrap database operations and API calls in try/except
- Rollback DB transactions on errors: `db.session.rollback()`
- Return JSON error responses with appropriate status codes
- Log errors: `print(f"Error: {e}")` or proper logging
```python
try:
    db.session.add(obj)
    db.session.commit()
    return jsonify({"success": True})
except Exception as e:
    db.session.rollback()
    print(f"Error saving: {e}")
    return jsonify({"error": "Failed to save"}), 500
```

### Database & Models
- Define all models in `models.py` (not scattered across files)
- Specify table names explicitly: `__tablename__ = "users"`
- Use relationships where appropriate: `season_team = relationship("SeasonTeam", ...)`
- Query with SQLAlchemy ORM: `User.query.filter_by(username="test").first()`
- Join queries for complex data: `db.session.query(...).join(...).all()`

### Security
- Never commit secrets (use .env file, reference env.example)
- Validate user authentication: `if "user_id" not in session:`
- Check admin privileges: `if not is_admin_user(): return jsonify({"error": "Unauthorized"}), 401`
- Use secure password hashing: `generate_password_hash(password)`
- Sanitize filenames: `secure_filename(upload.filename)`
- SECRET_KEY must be set in production (fail if missing)

### File Structure
```
main.py              # Legacy entry point (keep for backward compatibility)
app.py              # Main application entry point
models.py           # All SQLAlchemy models
app/
  __init__.py       # App factory: create_app()
  routes/
    api.py          # API endpoints (Blueprint)
    admin.py        # Admin routes (Blueprint)
    public.py       # Public routes (Blueprint)
static/
  uploads/          # User uploads
  images/           # Static images
  sfx/              # Sound effects
templates/          # Jinja2 templates
```

### Environment Variables
Load from `.env` file using python-dotenv. Required in `.env`:
- `SECRET_KEY`: Flask secret key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- `DATABASE_URL`: PostgreSQL or SQLite connection string
- `FLASK_ENV`: development/production
- `PORT`: Server port (default 5000)
- `RENDER`: Set to "true" on Render deployment

### Helper Functions
Define small, reusable helper functions:
```python
def get_today() -> date:
    return date.today()

def is_admin_user() -> bool:
    username = session.get("username")
    if not username: return False
    user = User.query.filter_by(username=username).first()
    return user and user.is_admin
```

### JSON Responses
- Use `jsonify()` for all API responses
- Include success/error status: `{"success": True, "data": {...}}`
- Use HTTP status codes: 200 (success), 201 (created), 400 (bad request), 401 (unauthorized), 404 (not found), 500 (server error)

### Comments
- Keep comments brief and helpful
- Prioritize readable code over comments
- Add docstrings for non-obvious functions
- Use English for code comments (project has Swedish content in data/strings)

### Database Operations
- Always use `with app.app_context():` when running scripts directly
- Commit after each logical operation: `db.session.commit()`
- Rollback on error: `db.session.rollback()`
- Flush for IDs: `db.session.flush()`

### Working with Session
- Session-based authentication: `session["username"] = username`
- Session timeout handled in decorators (24 hour timeout)
- Clear session on logout: `session.clear()`
- Check auth: `if "user_id" not in session:`
