import logging
import time

from worker_app.collector import fetch_prices, publish_updates
from worker_app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

# TODO (fase 2): carregar items/cities do banco em vez de hardcoded.
_ITEMS = ["T4_BAG", "T5_MAIN_SWORD", "T4_ORE"]
_CITIES = ["Martlock", "Lymhurst", "Bridgewatch"]


def main() -> None:
    logger.info("worker iniciado, poll_interval=%ss", settings.poll_interval_seconds)
    while True:
        snapshots = fetch_prices(_ITEMS, _CITIES)
        if snapshots:
            publish_updates(snapshots)
            logger.info("publicados %s snapshots de preço", len(snapshots))
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
