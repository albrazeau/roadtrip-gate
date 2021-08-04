#!/bin/sh
python /app/gotmail.py 2>&1 > /app/gotmail.log &
flask run --host=0.0.0.0 --port=80