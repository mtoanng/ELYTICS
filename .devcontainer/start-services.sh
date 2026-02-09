#!/bin/bash

# Start Redis server in the background
redis-server --daemonize yes

cd /workspaces/TBP-HOLMES

# Start backend in tmux
tmux new-session -d -s backend 'python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000'

# Start frontend in tmux
tmux new-session -d -s frontend 'python frontend/app.py'