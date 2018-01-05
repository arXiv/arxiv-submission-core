# """Helper script to initialize the Thing database and add a few rows."""
#
# from datetime import datetime
# import click
# from submit.factory import create_web_app
# from submit.services import database
# from submit.domain import event, annotation, agent, submission
# from submit import events
#
# app = create_web_app()
# app.app_context().push()
#
#
# @app.cli.command()
# def populate_database():
#     """Initialize the search index."""
#
#     database.db.drop_all()
#     database.db.create_all()
#
#     a = agent.System(native_id=1)
#
#     d1 = datetime(year=2017, month=12, day=8, hour=8, minute=56, second=44)
#     d2 = datetime(year=2017, month=12, day=8, hour=8, minute=56, second=45)
#     d3 = datetime(year=2017, month=12, day=8, hour=8, minute=56, second=46)
#     d4 = datetime(year=2017, month=12, day=8, hour=8, minute=56, second=47)
#     d5 = datetime(year=2017, month=12, day=8, hour=8, minute=56, second=48)
#
#     e1 = event.CreateSubmissionEvent(creator=a, created=d1)
#
#     submission = e1.submission
#     #
#     e2 = event.UpdateMetadataEvent(creator=a, update_from=e1, data={'abstract': 'baz', 'title': 'Foo'}, created=d2)
#     e3 = event.RemoveSubmissionEvent(creator=a, update_from=e2, created=d3)
#     e4 = event.CreateCommentEvent(creator=a, update_from=e3, created=d4, data={'body': 'The foo comment'})
#     e5 = event.DeleteCommentEvent(creator=a, update_from=e4, created=d5, data={'comment_id': '0fb5d451e48604aeac6ba72a45957aa0'})
#     #
#     events.apply_events((e1, e2, e3, e4, e5))
#     print(e4.submission.comments)
#     # s = database.get_or_create_submission({'submission_id': e4.submission.id})[0]
#     # print(s.comments)
#     # for e in s.events:
#     #     print(e.__dict__)
#     #     print(e.creator)
#
#
# if __name__ == '__main__':
#     populate_database()
