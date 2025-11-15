#!/bin/bash

# Script to run Django backend server

# Activate virtual environment
source .venv/bin/activate

# Navigate to backend directory and run server
cd backend && python manage.py runserver 0.0.0.0:8000
