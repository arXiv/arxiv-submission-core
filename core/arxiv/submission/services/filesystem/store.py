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

"""
import os
import tarfile
import shutil

from flask import current_app

from .util import chmod_recurse, copy_with_mode


class ConfigurationError(RuntimeError):
    """A required parameter is invalid/missing from the application config."""


class SecurityError(RuntimeError):
    """Something suspicious happened."""


def store_source(submission_id: int, source_path: str, pdf_path: str,
                 log_path: str) -> None:
    """
    Deposit a source package into the legacy filesystem.

    Caution! Only call this with data that you trust!

    Parameters
    ----------
    submission_id : int
        Numeric submission ID. This is **not** the upload ID.
    source_path : str
        Path to a gzipped tarball containing the source package to deposit.
        E.g. source package retrieved from the file management service.

    Raises
    ------
    ConfigurationError
        Raised when required parameters are missing from the application
        config.

    """
    try:    # The legacy filesystem is a giant NFS volume.
        base_dir = current_app.config['LEGACY_FILESYSTEM_ROOT']
        dir_mode = current_app.config['LEGACY_FILESYSTEM_SOURCE_DIR_MODE']
        file_mode = current_app.config['LEGACY_FILESYSTEM_SOURCE_MODE']
        source_uid = current_app.config['LEGACY_FILESYSTEM_SOURCE_UID']
        source_gid = current_app.config['LEGACY_FILESYSTEM_SOURCE_GID']
    except KeyError as e:
        raise ConfigurationError('Missing parameters; check config') from e

    # Classic filesystem structure is:
    #  /{base dir}/{first 4 digits of submission id}/{submission id}
    shard_dir = os.path.join(base_dir, str(submission_id)[:4])
    source_dir = os.path.join(shard_dir, str(submission_id))

    # Make sure that we have a place to put the source files.
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)  # Recursively create directories.

    # Deposit the source package. The classic system expects a directory called
    # "src".
    tf = tarfile.open(source_path, 'r:gz')
    _check_for_malicious_paths(tf)
    tf.extractall(os.path.join(source_dir, 'src'), numeric_owner=True)

    # Set permissions/owner.
    chmod_recurse(os.path.join(source_dir, 'src'), dir_mode, file_mode,
                  source_uid, source_gid)
    copy_with_mode(pdf_path, os.path.join(source_dir, f'{submission_id}.pdf'),
                   file_mode)
    copy_with_mode(log_path, os.path.join(source_dir, 'source.log'), file_mode)


def get_source(submission_id: int) -> None:
    """Retrieve a submission source package from the filesystem."""
    raise RuntimeError("NG components MUST NOT use this module to access"
                       " submission content! Access is provided by the file"
                       " management service, via its API.")


def _check_for_malicious_paths(tf: tarfile.TarFile) -> None:
    """Look for inappropriate relative paths, and complain if found."""
    for member in tf.getmembers():
        if '..' in member.name or member.issym() or member.islnk():
            raise SecurityError("Contains relative paths or links; abort!")
