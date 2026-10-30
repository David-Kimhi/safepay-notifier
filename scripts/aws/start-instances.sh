#!/usr/bin/env bash
# start-instances — start stopped lab instances and show their new IP addresses.
#
# Usage (from repo root):
#   ./scripts/aws/start-instances.sh           # all lab instances
#   ./scripts/aws/start-instances.sh kafka     # only one component
set -euo pipefail

source "$(dirname "$0")/_common.sh"
require_aws_cli

component="${1:-}"
ids="$(lab_instance_ids stopped "${component}")"

if [[ -z "${ids}" ]]; then
  echo "No stopped lab instances found${component:+ for component '${component}'}."
  exit 0
fi

echo "==> Starting: ${ids}"
# shellcheck disable=SC2086  # intentional word splitting: one argument per instance ID
aws ec2 start-instances --instance-ids ${ids} \
  --query 'StartingInstances[].[InstanceId,CurrentState.Name]' --output text

echo "==> Waiting until running..."
# shellcheck disable=SC2086
aws ec2 wait instance-running --instance-ids ${ids}

"$(dirname "$0")/list-instances.sh"
