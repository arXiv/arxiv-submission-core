"""
Integration with legacy filesystem.

The goal of this app is to make sure that the NG submission system can put
files in the right place on the legacy filesystem when a submission is
finalized. Until moderation and publication are decoupled from the SFS
filesystem, we need to ensure that submission content ends up in expected
places for those components to continue to function correctly.

.. note::

   NG components MUST NOT use this module to read submission content! Access
   is provided by the file management service, via its API.

"""
