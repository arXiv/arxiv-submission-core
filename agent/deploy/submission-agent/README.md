# Deployment Instructions for submission-agent

To install submission-agent to the development namespace in the kubernetes cluster:

```
helm install ./ --name=submission-agent \
--tiller-namespace=development \
--set \
image.tag=0.7.2rc12-5-g673f3f4-3,\
redis.host=tasks-development.vekyzh.ng.0001.use1.cache.amazonaws.com,\
vault.host=<SEE_NOTES_BELOW>,\
classifier.host=arxiv-nexus.library.cornell.edu,\
database=submission-agent-development.c94unvnkztba.us-east-1.rds.amazonaws.com
```

This assumes that the requisite Vault roles and policies have already been installed.

To delete the pod, run:
```
helm del --purge submission-agent --tiller-namespace=development
```

Notes:
- `image.tag`: this refers to the tag in [dockerhub](https://hub.docker.com/repository/docker/arxiv/submission-agent)
- `vault.host`: the actual IP of the Vault host can be retrieved from most of the other pods, for example by running the following command on one of the existing pods, e.g.:
```
$ kubectl describe pod submission-ui-8447fff4b7-cbqc2 | grep VAULT_HOST
```
