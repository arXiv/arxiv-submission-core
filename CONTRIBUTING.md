# Contributing to the arXiv submission API project

Thanks for taking the time to contribute! This document provides guidelines for
contributing to the project. We are constantly improving our workflows and
processes, so we welcome your suggestions and feedback.

## Workflow

We use the [Gitflow branching model](https://www.atlassian.com/git/tutorials/comparing-workflows#gitflow-workflow).

We try to [avoid fast forwards](https://confluence.atlassian.com/bitbucket/git-fast-forwards-and-branch-management-329977726.html).

Commit messages should be short, and include the ticket that you're working on
(e.g. ``ARXIVNG-42``).

If you don't have a ticket, create one! A GitHub issue will suffice.

- Master branch is stable, production code. No pushing to master!
- Develop branch is accepted code that is generally documented and tested, but
  not yet released. You will generally not push to develop.
- When you start working on a ticket/issue, create a new branch from develop.
  The naming convention is: [ticket type]/[issue tag]. For example,
  ``story/ARXIVNG-108`` or ``task/issue-51``.
- To merge a completed feature/story/task/bug branch to develop, raise a pull
  request. Before a PR can be merged into develop:
  - You'll need at least one code review from another team member.
  - All of the tests should be passing.
- Once your PR is approved, it's generally up to you to merge it. This gives
  you an opportunity to make any small additional changes to the PR before
  merging. If the changes are significant, you should probably open a separate
  PR to address them, or solicit additional code review.

### Versions

- We use semantic versioning (http://semver.org/) for each subsystem,
  independently. Each subsystem lives in its own GitHub repository.
- As part of the planning process, tickets are added to releases in JIRA. We may
  also use GitHub labels and/or milestones.
- Releases are named using the shorthand name for a subsystem, followed by a
  hyphen, followed by the semantic version. For example: ``fulltext-1.2``.
- Versions are commemorated using
  [tags](https://git-scm.com/book/en/v2/Git-Basics-Tagging).
- Git tags include the semantic version only. For example, ``1.2``.
- When a new version is ready for release (e.g. alpha, beta, or final), a PR
  from develop to master is raised.
- At least one code review is required, and general input from the team should
  be solicited.
- If all tests pass (including staging, see below), and the code review passes,
  the PR is merged and a tag is applied to the merge commit.
- When a tag is pushed to GitHub, release nodes from the JIRA release are
  added to the release description on GitHub.

## Code style & quality goals

We aspire to adhere as closely as possible to
[PEP008](https://www.python.org/dev/peps/pep-0008/).

We use [Numpy style docstrings](https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt).

Use Pylint (https://www.pylint.org/) to check your code prior to raising a pull
request. See ``.pylintrc`` in the root of this repo for configuration. In
general, we aim for a score of 9/10 with those parameters.

### Type annotations

We use type [type hint annotations](https://docs.python.org/3/library/typing.html)
everywhere except for unit tests. You can use [mypy](http://mypy-lang.org/) to
perform static checking. A mypy configuration called ``mypy.ini`` can be
found in the root of this repo. We run mypy like this:

```bash
$ pipenv run mypy core metadata | grep -v "test.*" | grep -v "defined here"
```

Our goal for production-ready code is to have no errors or warnings. Because
type annotations are fairly new, and there are plenty of cases that mypy does
not handle very well, it's OK to use ``# type: ignore`` on lines that generate
errors, so long as you verify that those messages are not indicative of real
programming errors. If there is an open issue/ticket somewhere related to the
message (e.g. a bug report on the mypy project), include a link in a comment
nearby.


## Testing

We write unit tests using the built-in [unittest
module](https://docs.python.org/3/library/unittest.html). Tests should live
close to the code that they exercise.

We run tests using [Nose2](http://nose2.readthedocs.io/en/latest/). You should
also install coverage (http://coverage.readthedocs.io/en/latest/). Nose2 will
look for files that start with ``test`` in importable Python modules, and try
to load classes that extend ``unittest.TestCase``.

Our nose2 config is ``unittest.cfg`` in the root of this repository. The file
``.coveragerc`` configures test coverage calculations.

```bash
$ pipenv run nose2 --with-coverage
```

In general, we aim for 90% code coverage or better.

## Documentation

We use [Sphinx](http://www.sphinx-doc.org/en/stable/contents.html) to build
documentation. Sphinx reads source documents in
[reStructuredText](http://docutils.sourceforge.net/rst.html), which is pretty
close to markdown, and can generate HTML, PDF, LaTeX.

Sphinx provides an [autodoc
module](http://www.sphinx-doc.org/en/stable/ext/autodoc.html) that will read
PEP008-compliant docstrings and automagically generates reST sources for API
documentation.

Per code style guidelines (see above), all of our modules, classes,
functions/methods should have docstrings.

Additional documentation goes in the ``docs`` folder in each repository. It
should be written in reStructuredText markdown.

For user interfaces: include a screenshot of each of the major views provided
by the service in the ``docs/ui/screenshots``. Use the snake-case route name as
the filename, e.g. ``advanced_search.png``. These will aid verification during
User Interface Testing. Additional details on building and distributing
documentation to come shortly.
