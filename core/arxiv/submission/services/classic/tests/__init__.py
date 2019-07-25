"""
Integration tests for the classic database service.

These tests assume that SQLAlchemy's MySQL backend is implemented correctly:
instead of using a live MySQL database, they use an in-memory SQLite database.
This is mostly fine (they are intended to be more-or-less swappable). The one
iffy bit is the JSON datatype, which is not available by default in the SQLite
backend. We extend the SQLite engine with a JSON type in 
:mod:`arxiv.submission.services.classic.util`. End to end tests with a live 
MySQL database will provide more confidence in this area.
"""
