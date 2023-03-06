#!/bin/bash
set -e

if [ "${1:0:1}" = '-' ]; then
    set -- gunicorn manage:app "$@"
fi
if [ "$1" = 'manage' ]; then
    if ["${@:2}" != ""]; then
        gunicorn manage:app --worker-class gevent --capture-output --bind :9070 --timeout 120
    else
        gunicorn manage:app ${@:2}
    fi
else
    exec "$@"
fi