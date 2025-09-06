# SQLite User Authentication Setup

This project now includes user authentication with SQLite database integration. Follow these steps to set up and run the system.

## Prerequisites

1. **Python**: Python 3.8+ with pip
2. **Virtual Environment**: It's recommended to use a virtual environment

## Installation Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,*

# Gemini AI Settings (optional)
GEMINI_API_KEY=your-gemini-api-key-here
```

### 3. Database Setup

The system uses SQLite by default, which is included with Django. No additional database setup is required.

### 4. Database Migration

Run the following commands to set up the database:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Initial User

Run the setup script to create your first user:

```bash
python setup_database.py
```

### 6. Run the Server

```bash
python manage.py runserver
```

## Features

### User Authentication

- **User Registration**: Users can create accounts with name, email, and password
- **User Login**: Secure login with email and password
- **Session Management**: Automatic session handling for logged-in users
- **Password Security**: Passwords are hashed using Django's built-in password hashing

### API Endpoints

- `POST /api/auth/login/` - User login
- `POST /api/auth/register/` - User registration
- `GET /api/auth/check/` - Check authentication status
- `POST /api/auth/logout/` - User logout

### Database Schema

The User model includes:
- `name`: Full name of the user
- `email`: Unique email address
- `password`: Hashed password
- `created_at`: Account creation timestamp
- `updated_at`: Last update timestamp

## Usage

### Creating an Account

1. Navigate to `/create-account/`
2. Fill in your name, email, and password
3. Click "Create Account"
4. You'll be redirected to the main page upon success

### Logging In

1. Navigate to `/login/`
2. Enter your email and password
3. Click "Sign In"
4. You'll be redirected to the main page upon success

### Security Features

- CSRF protection disabled for API endpoints (can be enabled for production)
- Password hashing using Django's secure hashing algorithms
- Session-based authentication
- Input validation and sanitization
- Error handling with user-friendly messages

## Troubleshooting

### Database Issues

1. Make sure all dependencies are installed
2. Run migrations: `python manage.py migrate`
3. Check if the database file exists: `db.sqlite3`

### Authentication Issues

1. Check browser console for JavaScript errors
2. Verify the API endpoints are accessible
3. Check Django server logs for backend errors

## Production Considerations

1. **Security**: Enable CSRF protection for production
2. **Environment Variables**: Use strong, unique secret keys
3. **Database**: Consider using PostgreSQL or MySQL for production
4. **HTTPS**: Use HTTPS in production for secure data transmission
5. **Session Security**: Configure secure session settings
