---
name: python-design-patterns
description: Python design patterns including KISS, Separation of Concerns, Single Responsibility, and composition over inheritance. Use when making architecture decisions, refactoring code structure, or evaluating when abstractions are appropriate.
---

# Python Design Patterns

Write maintainable Python code using fundamental design principles. These patterns help you build systems that are easy to understand, test, and modify.

## When to Use This Skill

- Designing new components or services
- Refactoring complex or tangled code
- Deciding whether to create an abstraction
- Choosing between inheritance and composition
- Evaluating code complexity and coupling
- Planning modular architectures

## Core Concepts

### 1. KISS (Keep It Simple)

Choose the simplest solution that works. Complexity must be justified by concrete requirements.

### 2. Single Responsibility (SRP)

Each unit should have one reason to change. Separate concerns into focused components.

### 3. Composition Over Inheritance

Build behavior by combining objects, not extending classes.

### 4. Rule of Three

Wait until you have three instances before abstracting. Duplication is often better than premature abstraction.

## Quick Start

```python
# Simple beats clever
# Instead of a factory/registry pattern:
FORMATTERS = {"json": JsonFormatter, "csv": CsvFormatter}

def get_formatter(name: str) -> Formatter:
    return FORMATTERS[name]()
```

## Fundamental Patterns

### Pattern 1: KISS - Keep It Simple

Before adding complexity, ask: does a simpler solution work?

```python
# Over-engineered: Factory with registration
class OutputFormatterFactory:
    _formatters: dict[str, type[Formatter]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(formatter_cls):
            cls._formatters[name] = formatter_cls
            return formatter_cls
        return decorator

    @classmethod
    def create(cls, name: str) -> Formatter:
        return cls._formatters[name]()

@OutputFormatterFactory.register("json")
class JsonFormatter(Formatter):
    ...

# Simple: Just use a dictionary
FORMATTERS = {
    "json": JsonFormatter,
    "csv": CsvFormatter,
    "xml": XmlFormatter,
}

def get_formatter(name: str) -> Formatter:
    """Get formatter by name."""
    if name not in FORMATTERS:
        raise ValueError(f"Unknown format: {name}")
    return FORMATTERS[name]()
```

The factory pattern adds code without adding value here. Save patterns for when they solve real problems.

### Pattern 2: Single Responsibility Principle

Each class or function should have one reason to change.

```python
# BAD: Handler does everything
class UserHandler:
    async def create_user(self, request: Request) -> Response:
        # HTTP parsing
        data = await request.json()

        # Validation
        if not data.get("email"):
            return Response({"error": "email required"}, status=400)

        # Database access
        user = await db.execute(
            "INSERT INTO users (email, name) VALUES ($1, $2) RETURNING *",
            data["email"], data["name"]
        )

        # Response formatting
        return Response({"id": user.id, "email": user.email}, status=201)

# GOOD: Separated concerns
class UserService:
    """Business logic only."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def create_user(self, data: CreateUserInput) -> User:
        # Only business rules here
        user = User(email=data.email, name=data.name)
        return await self._repo.save(user)

class UserHandler:
    """HTTP concerns only."""

    def __init__(self, service: UserService) -> None:
        self._service = service

    async def create_user(self, request: Request) -> Response:
        data = CreateUserInput(**(await request.json()))
        user = await self._service.create_user(data)
        return Response(user.to_dict(), status=201)
```

Now HTTP changes don't affect business logic, and vice versa.

### Pattern 3: Separation of Concerns

Organize code into distinct layers with clear responsibilities.

```
┌─────────────────────────────────────────────────────┐
│  API Layer (handlers)                                │
│  - Parse requests                                    │
│  - Call services                                     │
│  - Format responses                                  │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  Service Layer (business logic)                      │
│  - Domain rules and validation                       │
│  - Orchestrate operations                            │
│  - Pure functions where possible                     │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  Repository Layer (data access)                      │
│  - SQL queries                                       │
│  - External API calls                                │
│  - Cache operations                                  │
└─────────────────────────────────────────────────────┘
```

Each layer depends only on layers below it:

```python
# Repository: Data access
class UserRepository:
    async def get_by_id(self, user_id: str) -> User | None:
        row = await self._db.fetchrow(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        return User(**row) if row else None

# Service: Business logic
class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def get_user(self, user_id: str) -> User:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

# Handler: HTTP concerns
@app.get("/users/{user_id}")
async def get_user(user_id: str) -> UserResponse:
    user = await user_service.get_user(user_id)
    return UserResponse.from_user(user)
```

### Pattern 4: Composition Over Inheritance

Build behavior by combining objects rather than inheriting.

```python
# Inheritance: Rigid and hard to test
class EmailNotificationService(NotificationService):
    def __init__(self):
        super().__init__()
        self._smtp = SmtpClient()  # Hard to mock

    def notify(self, user: User, message: str) -> None:
        self._smtp.send(user.email, message)

# Composition: Flexible and testable
class NotificationService:
    """Send notifications via multiple channels."""

    def __init__(
        self,
        email_sender: EmailSender,
        sms_sender: SmsSender | None = None,
        push_sender: PushSender | None = None,
    ) -> None:
        self._email = email_sender
        self._sms = sms_sender
        self._push = push_sender

    async def notify(
        self,
        user: User,
        message: str,
        channels: set[str] | None = None,
    ) -> None:
        channels = channels or {"email"}

        if "email" in channels:
            await self._email.send(user.email, message)

        if "sms" in channels and self._sms and user.phone:
            await self._sms.send(user.phone, message)

        if "push" in channels and self._push and user.device_token:
            await self._push.send(user.device_token, message)

# Easy to test with fakes
service = NotificationService(
    email_sender=FakeEmailSender(),
    sms_sender=FakeSmsSender(),
)
```

## Advanced Patterns

### Pattern 5: Rule of Three

Wait until you have three instances before abstracting.

```python
# Two similar functions? Don't abstract yet
def process_orders(orders: list[Order]) -> list[Result]:
    results = []
    for order in orders:
        validated = validate_order(order)
        result = process_validated_order(validated)
        results.append(result)
    return results

def process_returns(returns: list[Return]) -> list[Result]:
    results = []
    for ret in returns:
        validated = validate_return(ret)
        result = process_validated_return(validated)
        results.append(result)
    return results

# These look similar, but wait! Are they actually the same?
# Different validation, different processing, different errors...
# Duplication is often better than the wrong abstraction

# Only after a third case, consider if there's a real pattern
# But even then, sometimes explicit is better than abstract
```

### Pattern 6: Function Size Guidelines

Keep functions focused. Extract when a function:

- Exceeds 20-50 lines (varies by complexity)
- Serves multiple distinct purposes
- Has deeply nested logic (3+ levels)

```python
# Too long, multiple concerns mixed
def process_order(order: Order) -> Result:
    # 50 lines of validation...
    # 30 lines of inventory check...
    # 40 lines of payment processing...
    # 20 lines of notification...
    pass

# Better: Composed from focused functions
def process_order(order: Order) -> Result:
    """Process a customer order through the complete workflow."""
    validate_order(order)
    reserve_inventory(order)
    payment_result = charge_payment(order)
    send_confirmation(order, payment_result)
    return Result(success=True, order_id=order.id)
```

### Pattern 7: Dependency Injection

Pass dependencies through constructors for testability.

```python
from typing import Protocol

class Logger(Protocol):
    def info(self, msg: str, **kwargs) -> None: ...
    def error(self, msg: str, **kwargs) -> None: ...

class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...

class UserService:
    """Service with injected dependencies."""

    def __init__(
        self,
        repository: UserRepository,
        cache: Cache,
        logger: Logger,
    ) -> None:
        self._repo = repository
        self._cache = cache
        self._logger = logger

    async def get_user(self, user_id: str) -> User:
        # Check cache first
        cached = await self._cache.get(f"user:{user_id}")
        if cached:
            self._logger.info("Cache hit", user_id=user_id)
            return User.from_json(cached)

        # Fetch from database
        user = await self._repo.get_by_id(user_id)
        if user:
            await self._cache.set(f"user:{user_id}", user.to_json(), ttl=300)

        return user

# Production
service = UserService(
    repository=PostgresUserRepository(db),
    cache=RedisCache(redis),
    logger=StructlogLogger(),
)

# Testing
service = UserService(
    repository=InMemoryUserRepository(),
    cache=FakeCache(),
    logger=NullLogger(),
)
```

### Pattern 8: Avoiding Common Anti-Patterns

**Don't expose internal types:**

```python
# BAD: Leaking ORM model to API
@app.get("/users/{id}")
def get_user(id: str) -> UserModel:  # SQLAlchemy model
    return db.query(UserModel).get(id)

# GOOD: Use response schemas
@app.get("/users/{id}")
def get_user(id: str) -> UserResponse:
    user = db.query(UserModel).get(id)
    return UserResponse.from_orm(user)
```

**Don't mix I/O with business logic:**

```python
# BAD: SQL embedded in business logic
def calculate_discount(user_id: str) -> float:
    user = db.query("SELECT * FROM users WHERE id = ?", user_id)
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user_id)
    # Business logic mixed with data access

# GOOD: Repository pattern
def calculate_discount(user: User, order_history: list[Order]) -> float:
    # Pure business logic, easily testable
    if len(order_history) > 10:
        return 0.15
    return 0.0
```

## Best Practices Summary

1. **Keep it simple** - Choose the simplest solution that works
2. **Single responsibility** - Each unit has one reason to change
3. **Separate concerns** - Distinct layers with clear purposes
4. **Compose, don't inherit** - Combine objects for flexibility
5. **Rule of three** - Wait before abstracting
6. **Keep functions small** - 20-50 lines (varies by complexity), one purpose
7. **Inject dependencies** - Constructor injection for testability
8. **Delete before abstracting** - Remove dead code, then consider patterns
9. **Test each layer** - Isolated tests for each concern
10. **Explicit over clever** - Readable code beats elegant code

---

## Project Conventions

These conventions apply to all code written for this project. They supplement the patterns above and must be followed consistently.

### String Quoting

Use **single quotes** by default. Switch to double quotes only when necessary — never escape quotes with backslashes.

```python
# GOOD: single quotes by default
name = 'hello world'
path = 'yt-audio/mp3'

# GOOD: double quotes when the string contains a single quote
msg = "it's done"
label = "don't skip this"

# BAD: escaping with backslash — never do this
msg = 'it\'s done'

# GOOD: docstrings always use double quotes
def process(name: str) -> str:
    """Process the given name and return a cleaned version."""
    return name.strip()
```

**Rules:**
- Single quotes for all regular strings
- Double quotes for docstrings (always)
- Double quotes when the string contains a single quote (avoids escaping)
- Never escape single or double quotes with a backslash

### Date and Time Parsing

Always use the `arrow` package for parsing and formatting dates/times. Never use `datetime.strptime` or similar directly.

```python
import arrow

# GOOD
dt = arrow.get('2026-02-28', 'YYYY-MM-DD')
formatted = dt.format('YYYY-MM-DD-HHmm')

# BAD
from datetime import datetime
dt = datetime.strptime('2026-02-28', '%Y-%m-%d')
```

### argparse Conventions

```python
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()

# GOOD: use %(default)s — never hardcode the default value in the help string
parser.add_argument('--retries', type=int, default=100,
                    help='Number of download retries (default: %(default)s)')

# GOOD: use type=Path for file/directory arguments — argparse validates existence
parser.add_argument('--output-dir', type=Path,
                    help='Output directory (default: %(default)s)')

# BAD: hardcoded default in help string
parser.add_argument('--retries', type=int, default=100,
                    help='Number of download retries (default: 100)')
```

### Keyword Arguments for Typed Functions

When calling a function whose signature has type hints, pass arguments as keyword arguments.

```python
def process_audio(input_path: Path, output_dir: Path, format: str = 'mp3') -> Path:
    ...

# GOOD: keyword arguments
result = process_audio(input_path=src, output_dir=dest, format='flac')

# BAD: positional arguments when the signature has type hints
result = process_audio(src, dest, 'flac')
```

### Path Handling

Use `pathlib.Path` for all file and directory operations. Never use `os.path`.

```python
from pathlib import Path

# GOOD
output = Path('yt-audio') / 'mp3' / filename
output.mkdir(parents=True, exist_ok=True)
resolved = some_path.resolve()

# BAD
import os
output = os.path.join('yt-audio', 'mp3', filename)
os.makedirs(output, exist_ok=True)
resolved = os.path.abspath(some_path)
```

**Exception:** `os.getenv()` is fine for reading environment variables — it is not a path operation.

### Omit `else` After Early Exit

When the last statement in an `if` block is `return` or `sys.exit()`, drop the `else`.

```python
# GOOD: no else needed
def get_format(name: str) -> str:
    if name not in SUPPORTED:
        print(f'Unknown format: {name}')
        sys.exit(1)
    return SUPPORTED[name]

# BAD: unnecessary else
def get_format(name: str) -> str:
    if name not in SUPPORTED:
        print(f'Unknown format: {name}')
        sys.exit(1)
    else:
        return SUPPORTED[name]
```

### Code Organization Order

Within a module, place definitions in this order:

1. Imports
2. Constants and global variables
3. Class definitions
4. Private/helper functions (names starting with `_`)
5. Public functions

```python
# GOOD order
SUPPORTED_FORMATS = ['mp3', 'm4a', 'flac']

class AudioProcessor:
    ...

def _validate_format(fmt: str) -> bool:   # private helper first
    return fmt in SUPPORTED_FORMATS

def process_audio(fmt: str) -> None:      # public function after
    if not _validate_format(fmt):
        raise ValueError(f'Unsupported format: {fmt}')
    ...
```

### Platform-Aware Executables

External tools have different locations depending on the platform:

```python
import platform
from pathlib import Path

def get_executable(name: str) -> str:
    """Return the path to an external executable."""
    if platform.system() == 'Windows':
        # Windows: executables are in a dedicated directory
        return str(Path.home() / 'Apps' / 'yt-dlp' / f'{name}.exe')
    # Linux/WSL/macOS: executables are on $PATH
    return name
```

### Case-Insensitive File Extensions (Linux/WSL/Mac)

On Linux/WSL/macOS, file extension matching must be case-insensitive. Use `.lower()` when comparing extensions.

```python
from pathlib import Path

def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in {'.mp3', '.m4a', '.flac'}

# GOOD: suffix.lower() covers .MP3, .Mp3, .mp3, etc.
files = [p for p in output_dir.iterdir() if p.suffix.lower() == '.mp3']
```

### Type Hints

All functions must have complete type annotations — parameters and return type.

```python
# GOOD
def sanitize_filename(name: str, max_length: int = 200) -> str:
    ...

def find_artist(text: str, artists: list[str]) -> str | None:
    ...

# BAD: missing annotations
def sanitize_filename(name, max_length=200):
    ...
```

Use `Path | str` for parameters that reasonably accept either type, and convert to `Path` early inside the function.