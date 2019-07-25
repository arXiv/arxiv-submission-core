"""
Functions for storing and getting (not!) source packages from the filesystem.

In the classic system we use a giant shared volume, which we'll call
``LEGACY_FILESYSTEM_ROOT`` in this package. Inside of that, what we'll call a
"shard id" (the first four digits of the submission ID) is used to create a
directory that in turn holds a directory for each submission.

For example, submission ``65393829`` would have a directory at
``{LEGACY_FILESYSTEM_ROOT}/6539/65393829``.

The submission directory contains a PDF that was compiled during the preview
step of submission, a ``source.log`` file from the file management service
(for the admins to look at), and a ``src`` directory that contains the actual
submission content.

We also require the ability to set permissions on files and directories, and
set the owner user and group.

To use this in a Flask application, the following config parameters must be
set:

- ``LEGACY_FILESYSTEM_ROOT``: (see above)
- ``LEGACY_FILESYSTEM_SOURCE_DIR_MODE``: permissions for directories; see
  :ref:`python:os.chmod`
- ``LEGACY_FILESYSTEM_SOURCE_MODE``: permissions for files; see
  :ref:`python:os.chmod`
- ``LEGACY_FILESYSTEM_SOURCE_UID``: uid for owner user (must exist)
- ``LEGACY_FILESYSTEM_SOURCE_GID``: gid for owner group (must exist)
- ``LEGACY_FILESYSTEM_SOURCE_PREFIX``

"""
import os
import tarfile
import shutil
from typing import IO
from subprocess import Popen
from hashlib import md5
from base64 import urlsafe_b64encode

from flask import current_app
from werkzeug.datastructures import FileStorage


class ConfigurationError(RuntimeError):
    """A required parameter is invalid/missing from the application config."""


class SecurityError(RuntimeError):
    """Something suspicious happened."""


def get_source(submission_id: int) -> None:
    """Retrieve a submission source package from the filesystem."""
    raise RuntimeError("NG components MUST NOT use this module to access"
                       " submission content! Access is provided by the file"
                       " management service, via its API.")


def is_available() -> bool:
    try:
        base_dir = current_app.config['LEGACY_FILESYSTEM_ROOT']
    except KeyError as e:
        raise ConfigurationError(f'Missing required config params: {e}') from e
    return os.path.exists(base_dir)


def store_source(submission_id: int, content: IO[bytes],
                 chunk_size: int = 4096) -> str:
    # Make sure that we have a place to put the source files.
    package_path = _source_package_path(submission_id)
    source_path = _source_path(submission_id)
    if not os.path.exists(package_path):
        os.makedirs(os.path.split(package_path)[0])
    if not os.path.exists(source_path):
        os.makedirs(source_path)

    with open(package_path, 'wb') as f:
        while True:
            chunk = content.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)

    _unpack_tarfile(package_path, source_path)
    _set_modes(package_path)
    _set_modes(source_path)
    return get_source_checksum(submission_id)


def store_preview(submission_id: int, content: IO[bytes],
                  chunk_size: int = 4096) -> str:
    preview_path = _preview_path(submission_id)
    if not os.path.exists(preview_path):
        os.makedirs(os.path.split(preview_path)[0])
    with open(preview_path, 'wb') as f:
        while True:
            chunk = content.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
    _set_modes(preview_path)
    return get_preview_checksum(submission_id)


def get_source_checksum(submission_id: int) -> str:
    return _get_checksum(_source_package_path(submission_id))


def source_exists(submission_id: int) -> bool:
    return os.path.exists(_source_package_path(submission_id))


def get_preview_checksum(submission_id: int) -> str:
    return _get_checksum(_preview_path(submission_id))


def preview_exists(submission_id: int) -> bool:
    return os.path.exists(_preview_path(submission_id))


# Just because we have a type check here does not mean that it is impossible
# for ``submission_id`` to be something other than an ``int``. Since I'm
# paranoid, we'll do a final check here to eliminate the possibility that a
# (potentially dangerous) ``str``-like value sneaks by.
def _validate_submission_id(submission_id: int) -> None:
    if not isinstance(submission_id, int):
        raise SecurityError('Submission ID is improperly typed. This is a'
                            ' security concern.')


# Classic filesystem structure is:
#  /{base dir}/{first 4 digits of submission id}/{submission id}
def _submission_path(submission_id: int) -> str:
    _validate_submission_id(submission_id)
    try:
        base_dir = current_app.config['LEGACY_FILESYSTEM_ROOT']
    except KeyError as e:
        raise ConfigurationError(f'Missing required config params: {e}') from e
    shard_dir = os.path.join(base_dir, str(submission_id)[:4])
    return os.path.join(shard_dir, str(submission_id))


# The classic system expects a directory called "src".
def _source_path(submission_id: int) -> str:
    _validate_submission_id(submission_id)
    try:
        source_prefix = current_app.config['LEGACY_FILESYSTEM_SOURCE_PREFIX']
    except KeyError as e:
        raise ConfigurationError(f'Missing required config params: {e}') from e
    return os.path.join(_submission_path(submission_id), source_prefix)


def _source_package_path(submission_id: int) -> str:
    _validate_submission_id(submission_id)
    preview_fname = f'{submission_id}.tar.gz'
    return os.path.join(_submission_path(submission_id), preview_fname)


def _preview_path(submission_id: int) -> str:
    _validate_submission_id(submission_id)
    preview_fname = f'{submission_id}.pdf'
    return os.path.join(_submission_path(submission_id), preview_fname)


def _get_checksum(path: str) -> str:
    hash_md5 = md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')


def _unpack_tarfile(tar_path: str, unpack_to: str) -> None:
    result = Popen(['tar', '-xzf', tar_path, '-C', unpack_to]).wait()
    if result != 0:
        raise RuntimeError(f'tar exited with {result}')


def _chmod_recurse(parent: str, dir_mode: int, file_mode: int,
                  uid: int, gid: int) -> None:
    """
    Recursively chmod and chown all directories and files.

    Parameters
    ----------
    parent : str
        Root directory for the operation (included).
    dir_mode : int
        Mode to set directories.
    file_mode : int
        Mode to set files.
    uid : int
        UID for chown.
    gid : int
        GID for chown.

    """
    if not os.path.isdir(parent):
        os.chown(parent, uid, gid)
        os.chmod(parent, file_mode)
        return

    for path, directories, files in os.walk(parent):
        for directory in directories:
            os.chown(os.path.join(path, directory), uid, gid)
            os.chmod(os.path.join(path, directory), dir_mode)
        for fname in files:
            os.chown(os.path.join(path, fname), uid, gid)
            os.chmod(os.path.join(path, fname), file_mode)
    os.chown(parent, uid, gid)
    os.chmod(parent, dir_mode)


def _set_modes(path: str) -> None:
    try:
        dir_mode = current_app.config['LEGACY_FILESYSTEM_SOURCE_DIR_MODE']
        file_mode = current_app.config['LEGACY_FILESYSTEM_SOURCE_MODE']
        source_uid = current_app.config['LEGACY_FILESYSTEM_SOURCE_UID']
        source_gid = current_app.config['LEGACY_FILESYSTEM_SOURCE_GID']
    except KeyError as e:
        raise ConfigurationError(f'Missing required config params: {e}') from e
    _chmod_recurse(path, dir_mode, file_mode, source_uid, source_gid)