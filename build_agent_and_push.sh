#!/bin/bash
# Development Only
#
# Build and push Docker image to Google Container Repository.
#
# Expects version in form v\d.\d as v1.0.
#

image_name="submission-agent"

echo "Build development docker image as version $1"

if [[ $1 =~ [0-9]\.[0-9] ]]; then
    echo "Version '$1' is OK"
else
    echo "Invalid version number: $1"

    # List existing image versions
    gcloud container images list-tags gcr.io/arxiv-compiler-dev/$image_name

    exit
fi

version=$1

#echo $version > compiler/version.py

# Build it!
docker build -t "$image_name:$version" .

# Tag it.
docker tag $image_name:$1 gcr.io/arxiv-compiler-dev/$image_name:$version

# Push it.
docker push gcr.io/arxiv-compiler-dev/$image_name:$version

# Update deployment 
#echo "Enter 'y' to set image for compiler api and worker (update Google Cloud Kubernetes)"
#read -r -p "Are You Sure? [Y/n] " response
#if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
#    then
#    # Update compiler API
#    kubectl set image deployment.apps/compiler-api arxiv-compiler=gcr.io/arxiv-compiler-dev/arxiv-compiler:$version
#    # Update worker
#    kubectl set image deployment.apps/compiler-worker arxiv-compiler=gcr.io/arxiv-compiler-dev/arxiv-compiler:$version
#fi

# List current containers
gcloud container images list-tags gcr.io/arxiv-compiler-dev/$image_name

