#!/usr/bin/env bash
# Shared helpers for the lab scripts. Sourced by the other scripts; not run directly.
#
# Environment:
#   PROJECT_TAG   Value of the "Project" tag that identifies lab instances
#                 (default: safepay-lab, set by the provider default_tags).
#   AWS_PROFILE / AWS_REGION   Standard AWS CLI selection of account and region.

set -euo pipefail

PROJECT_TAG="${PROJECT_TAG:-safepay-lab}"

require_aws_cli() {
  if ! command -v aws >/dev/null 2>&1; then
    echo "error: AWS CLI not found. Install it with: brew install awscli" >&2
    exit 1
  fi
}

# Print space-separated IDs of lab instances in the given state.
# Usage: lab_instance_ids <state> [component]
lab_instance_ids() {
  local state="$1"
  local component="${2:-}"
  local filters=(
    "Name=tag:Project,Values=${PROJECT_TAG}"
    "Name=instance-state-name,Values=${state}"
  )

  if [[ -n "${component}" ]]; then
    filters+=("Name=tag:Component,Values=${component}")
  fi

  aws ec2 describe-instances \
    --filters "${filters[@]}" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text
}
