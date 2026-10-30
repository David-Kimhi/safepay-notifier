#!/usr/bin/env bash
# stop-instances — stop running lab instances (compute billing stops, EBS disks still bill).
#
# Usage (from repo root):
#   ./scripts/aws/stop-instances.sh            # all lab instances
#   ./scripts/aws/stop-instances.sh kafka      # only one component
#
# Public IPs change after the next start; private IPs do not.
set -euo pipefail

source "$(dirname "$0")/_common.sh"
require_aws_cli

component="${1:-}"
ids="$(lab_instance_ids running "${component}")"

if [[ -z "${ids}" ]]; then
  echo "No running lab instances found${component:+ for component '${component}'}."
  exit 0
fi

echo "==> Stopping: ${ids}"
# shellcheck disable=SC2086  # intentional word splitting: one argument per instance ID
aws ec2 stop-instances --instance-ids ${ids} \
  --query 'StoppingInstances[].[InstanceId,CurrentState.Name]' --output text

echo "==> Waiting until stopped..."
# shellcheck disable=SC2086
aws ec2 wait instance-stopped --instance-ids ${ids}
echo "==> Done."
