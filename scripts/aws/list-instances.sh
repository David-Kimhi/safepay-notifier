#!/usr/bin/env bash
# list-instances — show every lab instance with its state and IP addresses.
#
# Usage (from repo root):
#   ./scripts/aws/list-instances.sh
set -euo pipefail

source "$(dirname "$0")/_common.sh"
require_aws_cli

aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=${PROJECT_TAG}" \
            "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[].Instances[].[Tags[?Key==`Component`]|[0].Value,InstanceId,State.Name,InstanceType,PrivateIpAddress,PublicIpAddress]' \
  --output table
