#!/bin/sh

newsboat -c /config/cache.db -C /config/config -u /config/urls -x reload
python3 /scripts/podcast.py

cd /srv/
/scripts/toopus.sh --bitrate 32
r128gain -ros .
find . -depth -type d -empty -exec rmdir {} \;
