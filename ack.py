#
#
# def commit(self):
#     self.validate()
#     self.project()
#         self.persist()
#     return self.submission.guid
# with database.transaction():
# def persist(self):
#     event = database.apply_event(self.event_type, self.data, self.agent,
#                                  self.submission, self.timestamp)
#     self.event_id = event.guid
#
#
# from datetime import datetime
# from typing import Any
# from submit.services import database
#
# class Agent(object):
#     pass
#
#
# class System(Agent):
#     pass
#
#
# class Client(Agent):
#     pass
#
#
# class User(Agent):
#     pass
#
#
# class Event(object):
#     def __init__(self, submission: int, data: dict = {},
#                  annotation: Annotation = None) -> None:
#         self.data = data
#         self.submission = submission
#         self.annotation = annotation
#
#     def commit(self):
#         pass
#
#
#
# class MetadataUpdateEvent(Event):
#     def project(self, dryrun=False):
#         if dryrun:
#             obj = copy.deepcopy(self.submission)
#         else:
#             obj = self.submission
#         for key, value in self.data.items():
#             setattr(obj, key, value)
#         return obj
#
#     def get_validator(self, key):
#         return getattr(self, 'validate_%s' % key, None)
#
#     def validate(self):
#         for key, value in self.data.items():
#             field_validator = self.get_validator(key)
#             if field_validator:
#                 field_validator(value)
#         obj = self.project(dryrun=True)
#         if obj.state Submission.INVALID:
#             raise ValidationError('foo')
#
#
# class CreateProposalEvent(Event):
#     def project(self):
#         self.submission.add_annotation(Proposal, self.data)
#
#     def commit(self):
#
#
#
#
# class Annotation(object):
#     def __init__(self, submission, **data):
#         self.submission = submission
#         self.data = data
#
#
# class Flag(Annotation):
#     pass
#
#
# class Comment(Annotation):
#     pass
#
#
# class Proposal(Annotation):
#     def set_event_type(self, etype: type):
#         if not isinstance(etype, type):
#             raise TypeError('')
#         self.data['event_type'] = etype
#
#     def get_event_type(self):
#         return self.data['event_type']
#
#     event_type = property(set_event_type, get_event_type)
#
#
# class Submission(object):
#     INVALID = -1
#
#     @property
#     def state(self):
#         return 0
#
#     def add_annotation(self, annotation_type, data):
#         # Create annotation with type, submission id, annotation id.
#         pass
#
#     def remove_annotation(self, annotation):
#         # Delete annotation with type, submission id, annotation id.
#         pass
#
#
#
#
# class TypedAttribute(object):
#     def __init__(self, dtype: type, name: str, default: Any=None, **extra):
#         if not isinstance(default, dtype) and default is not None:
#             raise TypeError('Unexpected type for default value')
#         self.name = name
#         self.value = default
#         self.dtype = dtype
#         self.extra = extra
#
#     def __get__(self, instance, owner=None):
#         if instance is not None:
#             return self.value
#         return self
#
#     def __set__(self, instance, value):
#         if not isinstance(value, self.dtype):
#             raise TypeError('Invalid type for this attribute')
#         self.value = value
#         if hasattr(instance, 'changes'):
#             instance.changes[self.name] = self.value
#
#
# class SubmissionMetadata(object):
#     def __init__(self, uid, **data):
#         self.uid = uid
#         self.update(**data)
#         self.changes = {}
#
#     def update(self, **data):
#         for key, value in data.items():
#             setattr(self, key, value)
#
#     title = TypedAttribute(str, 'title')
#     abstract = TypedAttribute(str, 'abstract')
#
#     def as_event(self):
#         return MetadataUpdateEvent(submission=self.uid, data=self.changes)
#
#
# if __name__ == '__main__':
#     sub = SubmissionMetadata(uid=1, abstract='What')
#     sub.title = 'bob'
#     sub.title = 'foo'
#     sub.update(abstract='Why')
#     print(sub.title)
#     print(sub.changes)
#
#
# #
# #
# # class Event(object):
# #
# #     def __init__(self, data):
# #         self.data = data
# #         self.created = datetime.now()
# #
# #     def project(self, obj):
# #         obj.foo = data
# #         return obj
# #
# #     def validate(self, obj):
# #
# #
# #
# #
# #
# # def apply(obj, event):
# #     for past_event in get_event_sequence(obj, event_from=obj.latest, including=event):
# #         obj = past_event.project(obj)
# #     obj.save()
# #     store_event(obj, event)
