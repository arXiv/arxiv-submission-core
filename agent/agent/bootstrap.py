"""Bootstrap the agent database."""

import time
from arxiv.base import logging
from .factory import create_app
from .services import database

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        session = database.db.session
        wait = 2
        while True:
            try:
                session.execute('SELECT 1')
                break
            except Exception as e:
                logger.info(e)
                logger.info(f'...waiting {wait} seconds...')
                time.sleep(wait)
                wait *= 2
        logger.info('Initializing database')
        if not database.tables_exist():
            database.create_all()
        exit(0)
