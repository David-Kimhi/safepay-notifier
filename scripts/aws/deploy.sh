#!/usr/bin/env bash
# deploy — roll the stack out to the lab instances, one compose file per role.
#
# For each role it: resolves every instance's private IP from EC2 tags, then over
# SSM updates /opt/safepay to GIT_REF and runs `docker compose up -d --build` with
# that role's compose file. Roles are deployed in dependency order.
#
# Usage (from repo root):
#   ./scripts/aws/deploy.sh                 # all roles
#   ./scripts/aws/deploy.sh gateway worker  # selected roles
#
# Environment:
#   GIT_REF         Branch or tag to deploy (default: main).
#   WITH_PROMTAIL   1 = also ship logs from non-monitor roles to Loki on the monitor
#                   instance (needs the monitor security group to allow TCP 3100).
#   AWS_PROFILE / AWS_REGION   AWS CLI account and region.
set -euo pipefail

source "$(dirname "$0")/_common.sh"
require_aws_cli

# Dependency order: data layer first, then apps, then load and monitoring.
ALL_ROLES=(kafka postgres redis gateway worker load monitor)
GIT_REF="${GIT_REF:-main}"
WITH_PROMTAIL="${WITH_PROMTAIL:-0}"
APP_DIR="/opt/safepay"

roles=("$@")
if [[ ${#roles[@]} -eq 0 ]]; then
  roles=("${ALL_ROLES[@]}")
fi

for role in "${roles[@]}"; do
  if [[ " ${ALL_ROLES[*]} " != *" ${role} "* ]]; then
    echo "error: unknown role '${role}'. Valid roles: ${ALL_ROLES[*]}" >&2
    exit 1
  fi
done

echo "==> Resolving private IPs from EC2 tags (Project=${PROJECT_TAG})..."
host_vars=""
for role in "${ALL_ROLES[@]}"; do
  read -r _ private_ip <<<"$(lab_running_instance "${role}")"
  upper="$(echo "${role}" | tr '[:lower:]' '[:upper:]')"
  host_vars+=" ${upper}_HOST=${private_ip}"
  echo "    ${role}: ${private_ip}"
done

for role in "${roles[@]}"; do
  read -r instance_id _ <<<"$(lab_running_instance "${role}")"

  files="-f deploy/ec2/compose.${role}.yml"
  if [[ "${WITH_PROMTAIL}" == "1" && "${role}" != "monitor" ]]; then
    files+=" -f deploy/ec2/compose.promtail.yml"
  fi

  command="set -e; cd ${APP_DIR}; git fetch -q origin ${GIT_REF}; git reset -q --hard FETCH_HEAD; export ROLE=${role}${host_vars}; docker compose -p safepay ${files} up -d --build --remove-orphans; docker compose -p safepay ${files} ps"

  echo "==> [${role}] deploying ${GIT_REF} to ${instance_id}"
  ssm_run "${instance_id}" "${command}"
done

echo "==> Done."
