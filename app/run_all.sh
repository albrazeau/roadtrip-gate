#!/bin/sh
python /app/gotmail.py &
flask run --host=0.0.0.0 --port=80