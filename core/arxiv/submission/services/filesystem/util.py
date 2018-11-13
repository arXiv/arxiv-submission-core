import os
import shutil


def chmod_recurse(parent: str, dir_mode: int, file_mode: int,
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
    for path, directories, files in os.walk(parent):
        for directory in directories:
            os.chown(os.path.join(path, directory), uid, gid)
            os.chmod(os.path.join(path, directory), dir_mode)
        for fname in files:
            os.chown(os.path.join(path, fname), uid, gid)
            os.chmod(os.path.join(path, fname), file_mode)
    os.chown(parent, uid, gid)
    os.chmod(parent, dir_mode)


def copy_with_mode(source_path: str, dest_path: str, mode: int) -> None:
    """Copy a file from ``source_path`` to ``dest_path``, and set ``mode``."""
    shutil.copy(source_path, dest_path)
    os.chmod(dest_path, mode)
