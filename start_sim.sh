#!/bin/sh

uwsgi --http-socket :8002 --manage-script-name -w auth --ugreen &
/etc/init.d/nginx restart
uwsgi --http-socket :8001 --manage-script-name -w wsgi --ugreen
