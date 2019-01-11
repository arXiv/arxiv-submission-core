from unittest import TestCase, mock
from flask import Flask
from celery import Celery


class TestRulesWithAsync(TestCase):
    def setUp(self):
        self.app = Flask('test')
        self.celery = Celery('test', broker='memory', backend='memory')
