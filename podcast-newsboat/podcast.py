#!/usr/bin/env python
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from math import floor, log2
from pathlib import Path
from typing import Tuple

import requests


def human_size(x: int) -> str:
    if x == 0:
        return '0 B'
    suffixes = ['B', 'kiB', 'MiB', 'GiB', 'TiB']
    exponent = floor(log2(x) / 10) * 10
    x = x / 2 ** exponent
    suffix = suffixes[exponent // 10]
    return f'{x:.2f} {suffix}'


def download(url: str, location: Path) -> Tuple[bool, str, Path, int]:
    total_size, success = 0, False
    location.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, headers=headers) as r:
            try:
                total_size = int(r.headers.get('content-length'))
            except TypeError:
                print(f"No valid size for {url}")
                success = False
            else:
                with open(location, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1048576):
                        f.write(chunk)
                if total_size > 0:
                    if r.status_code != 200 or total_size != location.stat().st_size:
                        location.unlink()
                        success = False
                    else:
                        success = True
    except Exception:
        if location.exists():
            location.unlink
            success = False
    return success, url, location, total_size



headers = {
    'user-agent':
        'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0',
    'Accept-Encoding': 'gzip, deflate'
}

urls, locations = [], []

with open('/root/.newsboat/queue') as file:
    for line in file:
        line = line.replace(r'\"', '')
        first, second, _ = line.split('"')
        urls.append(first.rstrip())
        locations.append(
            Path(
                '/'.join(second.split('/')[: 7]) +
                ''.join(second.split('/')[7 :])
            )
        )

new_queue = []
total_size = 0

with ThreadPoolExecutor(max_workers=6) as executor:
    for success, url, location, size in executor.map(download, urls, locations):
        if not success:
            new_queue.append(f'{url} "{location}"\n')
        else:
            total_size += size

print(f"Total size is {human_size(total_size)}")

with open('/root/.newsboat/queue', 'w') as file:
    file.writelines(new_queue)
