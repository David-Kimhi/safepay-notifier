#!/usr/bin/env bash
# Shared helpers for the lab scripts. Sourced by the other scripts; not run directly.
#
# Environment:
#   PROJECT_TAG   Value of the "Project" tag that identifies lab instances
#                 (default: safepay-lab, set by the provider default_tags).
#   AWS_PROFILE / AWS_REGION   Standard AWS CLI selection of account and region.

set -euo pipefail

# Never open the AWS CLI's interactive pager (it would hang scripts on long output).
export AWS_PAGER=""

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

# Print "<instance-id> <private-ip>" of the running instance for a component.
# Usage: lab_running_instance <component>
lab_running_instance() {
  local component="$1"
  local result

  result="$(aws ec2 describe-instances \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" \
              "Name=tag:Component,Values=${component}" \
              "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].[InstanceId,PrivateIpAddress]' \
    --output text)"

  if [[ -z "${result}" || "${result}" == "None"* ]]; then
    echo "error: no running instance with Component=${component}" >&2
    return 1
  fi
  echo "${result}"
}

# Run a shell command on an instance through SSM and stream its output.
# The command must not contain double quotes or backslashes (it is embedded in JSON).
# Returns non-zero if the command fails.
# Usage: ssm_run <instance-id> <command>
ssm_run() {
  local instance_id="$1"
  local command="$2"
  local command_id status
  local attempts=0

  command_id="$(aws ssm send-command \
    --instance-ids "${instance_id}" \
    --document-name AWS-RunShellScript \
    --timeout-seconds 1800 \
    --parameters "{\"commands\":[\"${command}\"]}" \
    --query Command.CommandId --output text)"

  while true; do
    status="$(aws ssm get-command-invocation \
      --command-id "${command_id}" --instance-id "${instance_id}" \
      --query Status --output text 2>/dev/null || echo Pending)"
    case "${status}" in
      Pending|InProgress|Delayed) ;;
      *) break ;;
    esac
    attempts=$((attempts + 1))
    if [[ "${attempts}" -gt 600 ]]; then
      echo "error: timed out waiting for SSM command ${command_id}" >&2
      return 1
    fi
    sleep 3
  done

  aws ssm get-command-invocation \
    --command-id "${command_id}" --instance-id "${instance_id}" \
    --query StandardOutputContent --output text
  aws ssm get-command-invocation \
    --command-id "${command_id}" --instance-id "${instance_id}" \
    --query StandardErrorContent --output text >&2

  [[ "${status}" == "Success" ]]
}
