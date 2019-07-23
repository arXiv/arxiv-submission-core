# Legacy shim for source packages + PDF preview

This app provides a simple API for injecting source content and PDF previews
from the NG submission system into the legacy system.

It exposes two routes:

## ``/{submission id}/source``

The source package resource.

### ``POST``

Deposit source package.

### ``HEAD`` + ``GET``

Verify that source package is deposited. Does not return package content.

## ``/{submission id}/pdf``

The PDF preview resource.

### ``POST``

Deposit PDF preview.

### ``HEAD`` + ``GET``

Verify that PDF preview is deposited. Does not return PDF preview content.

