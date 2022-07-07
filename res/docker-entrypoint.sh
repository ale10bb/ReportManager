#!/bin/bash
set -e

if [ "${1:0:1}" = '-' ]; then
    set -- gunicorn minimal_web:app "$@"
fi
if [ "$1" = 'main' ]; then
    if ["${@:2}" != ""]; then
        gunicorn minimal_web:app --worker-class gevent --capture-output --bind :9070 --timeout 120
    else
        gunicorn minimal_web:app ${@:2}
    fi
else
    exec "$@"
fi