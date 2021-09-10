#!/bin/sh

set -ue

curl \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  --data-binary @hello.bin \
  ${ESP_ADDRESS}/prints
