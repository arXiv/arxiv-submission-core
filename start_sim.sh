#!/bin/sh

uwsgi --http-socket :8002 --manage-script-name -w auth --ugreen &
nginx
uwsgi --http-socket :8001 -w wsgi \
    -t 3000 \
    --processes 8 \
    --threads 1 \
    -M \
    --async 100 \
    --ugreen \
    --manage-script-name
