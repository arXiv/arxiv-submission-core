# Authorization service (demo)

The authorization service handles subrequests from the [gateway](../gateway)
to authorize API client requests. This implementation merely mocks the
functionality of a real authorization service for demonstration purposes.

## Example request lifecycle

A typical client request might go something like this...

```
Client     Gateway      Auth    API      Events        Broker
  | --POST--> |           |      |          |             |
  |  w/token  | --token-> |      |          |             |
  |           |           |      |          |             |
  |           | <--JWT--- |      |          |             |
  |           |                  |          |             |
  |           | --POST (w/JWT)-> |          |             |
  |           |    Submission    | --POST-> |             |
  |           |                  |  (w/JWT) | --Notify--> |  
  |           |                  | <--OK--- |   (async)   | --Notify--> ..
  |           | <------OK------- |
  | <---OK--- |
```
