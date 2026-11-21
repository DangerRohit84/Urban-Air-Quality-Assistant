"""Process-wide single-flight slot for PDF uploads.

The free-tier container has 512 MB of RAM, and each spawned PDF extraction can
add a few hundred MiB. Concurrent uploads can therefore exhaust memory, so the
upload route takes this slot before reading the multipart body and releases it
in a ``finally`` block. A caller that finds the slot busy is rejected with a
503 instead of queueing.
"""

from __future__ import annotations

import asyncio

BUSY_DETAIL = "server busy, retry shortly"
RETRY_AFTER_SECONDS = "2"
UPLOAD_SLOT = asyncio.Semaphore(1)
