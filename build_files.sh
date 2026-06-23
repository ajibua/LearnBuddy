#!/bin/bash
echo "Building project..."

# Create a temporary virtual environment
python3 -m venv temp_venv
source temp_venv/bin/activate

echo "Installing dependencies in temporary virtualenv..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Deactivating and cleaning up..."
deactivate
rm -rf temp_venv

echo "Build complete!"
