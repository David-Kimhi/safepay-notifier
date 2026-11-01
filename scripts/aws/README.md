# Lab scripts

Helper scripts for the SafePay EC2 lab (see [terraform/ec2](../../terraform/ec2/README.md)).
They use the AWS CLI and find instances by the `Project=safepay-lab` tag, so they
work independently of Terraform state.

Run them from the repo root. They use your current AWS CLI identity, so select
the account and region first, for example:

```sh
export AWS_PROFILE=default
export AWS_REGION=eu-north-1
```

| Script | What it does | Example |
|--------|--------------|---------|
| `list-instances.sh` | Lists lab instances with component, ID, state, type, and private/public IPs. | `./scripts/aws/list-instances.sh` |
| `stop-instances.sh [component]` | Stops running instances and waits until they are stopped. Compute billing stops; EBS disks keep billing. | `./scripts/aws/stop-instances.sh` |
| `start-instances.sh [component]` | Starts stopped instances, waits until they are running, then lists the new IPs. | `./scripts/aws/start-instances.sh kafka` |
| `bootstrap-instances.sh [role...]` | One-time setup over SSM: installs Docker and git and clones the repo to `/opt/safepay`. Safe to re-run. | `./scripts/aws/bootstrap-instances.sh` |
| `deploy.sh [role...]` | Looks up private IPs from EC2 tags, then updates each instance to `GIT_REF` and runs its compose file from [deploy/ec2](../../deploy/ec2/README.md). | `GIT_REF=main ./scripts/aws/deploy.sh gateway` |

`component` is one of `kafka`, `postgres`, `redis`, `gateway`, `worker`, `load`,
`monitor`. Omit it to act on all instances.

`_common.sh` holds shared helpers and is sourced by the other scripts.

## Scripts vs. Terraform

Power state can also be managed by Terraform (from `terraform/ec2`) through the
`instances_state` variable:

```sh
terraform apply -var="instances_state=stopped"
terraform apply -var="instances_state=running"
```

Pick one method per session. If you stop instances with these scripts while
Terraform's desired state is `running`, the next `terraform apply` starts them
again.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROJECT_TAG` | `safepay-lab` | `Project` tag value used to find lab instances. |
| `GIT_REF` | `main` | Branch or tag that `deploy.sh` checks out on the instances. |
| `WITH_PROMTAIL` | `0` | `1` makes `deploy.sh` ship logs from every role to Loki on the monitor instance. |
| `AWS_PROFILE`, `AWS_REGION` | AWS CLI defaults | Account and region to act on. |

## Useful one-liners

```sh
# Instance IDs as JSON, straight from Terraform
terraform output -json instance_ids

# Open a shell on an instance through Session Manager (needs the Session Manager plugin)
aws ssm start-session --target "$(terraform output -json instance_ids | python3 -c 'import json,sys; print(json.load(sys.stdin)["kafka"])')"
```
