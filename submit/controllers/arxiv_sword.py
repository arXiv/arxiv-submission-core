from datetime import datetime
from typing import Tuple
from flask import url_for, current_app
import sword
from submit import status
from submit.domain.event import event_factory
from submit.domain.agent import Agent, agent_factory
from submit import eventBus


ARXIV = 'http://arxiv.org/schema/terms/'

Response = Tuple[dict, int, dict]

NO_SUCH_ARCHIVE = (
    {'reason': 'No such archive'},
    status.HTTP_404_NOT_FOUND,
    {}
)
NO_USER_OR_CLIENT = (
    {'reason': 'Neither client nor user is set'},
    status.HTTP_400_BAD_REQUEST,
    {}
)


def _get_agent(extra: dict) -> Agent:
    user = extra.get('user')
    client = extra.get('client')
    if user:
        return agent_factory('UserAgent', user)
    elif client:
        return agent_factory('Client', client)
    return


class ArXivSWORDServiceDocument(sword.SWORDServiceDocument):
    def _list_collections(self):
        return [{
            ('sword', 'name'): cname,
            ('sword', 'endpoint'): url_for('submit.collection', archive=cname)
        } for cname in current_app.config['COLLECTIONS']]

    def _get_service(self, body: dict, headers: dict, files: dict=None,
                     extra: dict={}) -> Response:
        config = current_app.config
        return {
            ('sword', 'maxUploadSize'): config['MAX_UPLOAD_SIZE'],
            ('sword', 'maxByReferenceSize'): config['MAX_BY_REFERENCE_SIZE'],
            ('sword', 'treatment'): {
                ('sword', 'href'): config['TREATMENT_URI']
            },
            ('sword', 'collectionPolicy'): {
                ('sword', 'href'): config['COLLECTION_POLICY_URI']
            },
            ('sword', 'by-reference'): config['ALLOW_BY_REFERENCE'],
            ('sword', 'in-progress'): config['ALLOW_IN_PROGRESS'],
            ('sword', 'mediation'): config['ALLOW_MEDIATION'],
            ('sword', 'digest'): config['DIGEST_ALGORITHM'],
            ('sword', 'name'): 'arXiv'
        }, status.HTTP_200_OK, {}


class ArXivSWORDCollection(sword.SWORDCollection):
    def _add_submission(self, body: dict, headers: dict, files: dict=None,
                        extra: dict={}) -> Response:
        archive = extra.get('archive')
        if not archive:
            return NO_SUCH_ARCHIVE

        creator = _get_agent(extra)
        if not creator:
            return NO_USER_OR_CLIENT

        submission = eventBus.apply_events(
            event_factory(
                'CreateSubmissionEvent',
                creator=creator,
                created=datetime.now(),
                archive=archive
            ),
            # event_factory(
            #     'UpdateMetadataEvent',
            #     creator=creator,
            #     created=datetime.now(),
            #     metadata=dict(
            #         title=''
            #     )
            # )
        )
        headers = {
            'Location': url_for('submit.get_submission', archive=archive,
                                sub_id=submission.submission_id)
        }
        return body, status.HTTP_202_ACCEPTED, headers


class ArXivSWORDSubmission(sword.SWORDSubmission):
    def _get_status(self, body: dict, headers: dict, files: dict=None,
                    extra: dict={}) -> Response:
        archive = extra.get('archive')
        submission_id = extra.get('submission')
        submission, _ = eventBus.get_submission(submission_id)
        print(submission.__dict__)
        return submission.to_dict(), 200, {}


get_controller = sword.interface_factory([ArXivSWORDServiceDocument,
                                          ArXivSWORDCollection,
                                          ArXivSWORDSubmission])
