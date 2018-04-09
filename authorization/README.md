# Authorization service (demo)

The authorization service handles subrequests from the [gateway](../gateway)
to authorize API client requests. This implementation merely mocks the
functionality of a real authorization service for demonstration purposes.

## Example request lifecycle

A typical client request might go something like this...

```
Client     Gateway      Auth   Service
  | --POST--> |           |       |   
  |  w/token  | --token-> |       |   
  |           |           |       |   
  |           | <--JWT--- |       |   
  |           |                   |   
  |           | --POST (w/JWT)--> |   
  |           |    Submission     | --- // -->
  |           | <------OK-------- |
  | <---OK--- |
```
