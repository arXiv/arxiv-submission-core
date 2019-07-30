# Legacy filesystem integration shim

The goal of this app is to make sure that the NG submission system can put
files in the right place on the legacy filesystem when (and only when) a submission is
finalized. Until moderation and publication are decoupled from the SFS
filesystem, we need to ensure that submission content ends up in expected
places for those components to continue to function correctly.
