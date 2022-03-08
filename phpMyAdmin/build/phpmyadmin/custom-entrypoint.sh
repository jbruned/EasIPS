#!/bin/sh

# Copy over the saved files from /tmp/html to /var/www
cp -r /tmp/html /var/www

# Kick off the original entrypoint
exec /docker-entrypoint.sh "$@"
