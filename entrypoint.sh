#!/bin/bash
: "${API_KEY:?API_KEY must be set}"
trap exit TERM INT
/usr/sbin/cupsd -f &
/app/.venv/bin/python -m uvicorn epson_api.main:create_app --factory --host 0.0.0.0 --port 8000 &
wait -n
