#!/usr/bin/env bash
# bootstrap-instances — one-time setup of the lab instances through SSM:
# installs Docker + git and clones the repo to /opt/safepay. Safe to re-run.
#
# Usage (from repo root):
#   ./scripts/aws/bootstrap-instances.sh              # all roles
#   ./scripts/aws/bootstrap-instances.sh kafka redis  # selected roles
#
# Environment:
#   REPO_URL   Repository to clone (default: the public GitHub repo).
set -euo pipefail

source "$(dirname "$0")/_common.sh"
require_aws_cli

ALL_ROLES=(kafka postgres redis gateway worker load monitor)
REPO_URL="${REPO_URL:-https://github.com/David-Kimhi/safepay-notifier.git}"
APP_DIR="/opt/safepay"

roles=("$@")
if [[ ${#roles[@]} -eq 0 ]]; then
  roles=("${ALL_ROLES[@]}")
fi

command="set -e; export DEBIAN_FRONTEND=noninteractive; apt-get update -qq; apt-get install -y -qq docker.io docker-compose-v2 git; systemctl enable --now docker; [ -d ${APP_DIR}/.git ] || git clone ${REPO_URL} ${APP_DIR}; docker --version; docker compose version"

for role in "${roles[@]}"; do
  read -r instance_id _ <<<"$(lab_running_instance "${role}")"
  echo "==> [${role}] bootstrapping ${instance_id}"
  ssm_run "${instance_id}" "${command}"
done

echo "==> Done. Create deploy/ec2/.env on postgres, gateway, worker (and monitor) — see deploy/ec2/README.md."
