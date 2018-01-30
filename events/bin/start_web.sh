python3.6 create_db.py
uwsgi --http-socket :8000 -w wsgi -M \
        -t 3000 --manage-script-name \
        --processes 8 --threads 1 --async 100 --ugreen \
