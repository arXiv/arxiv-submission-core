"""Initialize the submission database."""
import time
from arxiv.base import logging
from metadata.factory import create_web_app
from arxiv.submission.services import classic
from arxiv.submission.services.classic import bootstrap

logger = logging.getLogger(__name__)


app = create_web_app()
with app.app_context():
    session = classic.current_session()
    engine = classic.current_engine()
    logger.info('Waiting for database server to be available')
    logger.info(app.config['CLASSIC_DATABASE_URI'])
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

    logger.info('Checking for database')
    if not engine.dialect.has_table(engine, 'arXiv_submissions'):
        logger.info('Database not yet initialized; creating tables')
        classic.create_all()

        logger.info('Populate with base data...')
        licenses = classic.bootstrap.licenses()
        for obj in licenses:
            session.add(obj)
        logger.info('Added %i licenses', len(licenses))
        policy_classes = classic.bootstrap.policy_classes()
        for obj in policy_classes:
            session.add(obj)
        logger.info('Added %i policy classes', len(policy_classes))
        categories = classic.bootstrap.categories()
        for obj in categories:
            session.add(obj)
        logger.info('Added %i categories', len(categories))
        users = classic.bootstrap.users()
        for obj in users:
            session.add(obj)
        logger.info('Added %i users', len(users))
        session.commit()

        exit(0)
    logger.info('Nothing to do')
