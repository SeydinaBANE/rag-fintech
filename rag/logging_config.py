import logging
import os

import sentry_sdk


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def configure_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    # Compliance-relevant: no stack-frame local variables (SQL results,
    # generated SQL) are ever sent to Sentry — this app handles fintech data.
    sentry_sdk.init(dsn=dsn, include_local_variables=False)
