#!/bin/sh
python3 /app/gotmail.py &
flask run --host=0.0.0.0 --port=80