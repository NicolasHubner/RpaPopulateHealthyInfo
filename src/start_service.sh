#!/bin/bash

# Set passwords
ES_PASSWORD="<ES_PASSWORD>"
KIBANA_PASSWORD="<KIB_PASSWORD>"

# Run Docker Compose
docker-compose up -d

# Wait for Elasticsearch to be fully up
echo "Waiting for Elasticsearch to start..."
until curl -u elastic:$ES_PASSWORD -X GET http://localhost:9200/_cluster/health?wait_for_status=yellow > /dev/null 2>&1; do
  sleep 5
done

# Run the curl command to set Kibana system user password
curl -u elastic:<ES_PASSWORD> \
  -X POST \
  http://localhost:9200/_security/user/kibana_system/_password \
  -d '{"password":"'"<KIB_PASSWORD>"'"}' \
  -H 'Content-Type: application/json'
