"""Platforms whose endpoints are being researched separately. Nothing here is guessed."""


def list_postings(source, fetcher, config):
    raise NotImplementedError(
        f"adapter for platform {source['platform']!r} not implemented: endpoint not yet confirmed")
