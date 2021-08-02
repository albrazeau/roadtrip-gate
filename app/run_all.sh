#!/bin/sh
python /app/pipeline.py &
flask run --host=0.0.0.0 --port=80