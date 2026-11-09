"""External data sources.

* :mod:`lse`    -- London Strategic Edge, LSE Data 3.0 REST API (intraday candles;
                   free key from the Databank, ``LSE_API_KEY``).
* :mod:`fred`   -- Federal Reserve Economic Data, keyless CSV endpoint.
* :mod:`french` -- Kenneth R. French data library (daily factor returns).

Every fetcher goes through :mod:`http`, a small urllib wrapper with retries
and an optional on-disk cache, so the package adds no dependencies.
"""
