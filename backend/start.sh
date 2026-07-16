#!/bin/sh
set -e

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Start ASGI server
echo "Starting Daphne ASGI server on port $PORT..."
daphne -b 0.0.0.0 -p $PORT config.asgi:application
