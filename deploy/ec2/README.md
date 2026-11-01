# EC2 deployment (one compose file per role)

The root `docker-compose.yml` runs everything on one machine. This directory
splits the stack across the seven lab instances created by
[terraform/ec2](../../terraform/ec2/README.md), one compose file per role, so the
services talk to each other over private IPs.

| Role | Compose file | Services |
|------|--------------|----------|
| kafka | `compose.kafka.yml` | zookeeper, kafka |
| postgres | `compose.postgres.yml` | postgres (schema from `postgres/init`) |
| redis | `compose.redis.yml` | redis |
| gateway | `compose.gateway.yml` | payment-gateway |
| worker | `compose.worker.yml` | webhook-worker, balance-reconciler |
| load | `compose.load.yml` | bank-simulator |
| monitor | `compose.monitor.yml` | prometheus, grafana, loki, promtail, cadvisor, akhq |
| any (optional) | `compose.promtail.yml` | promtail log shipper pointing at the monitor instance |

## How private IPs are provided

Compose files reference `${KAFKA_HOST}`, `${POSTGRES_HOST}`, `${REDIS_HOST}`,
`${GATEWAY_HOST}`, and so on. They are **not** read from `terraform output`: the
Terraform state lives on your machine, so CI could not read it. Instead
`scripts/aws/deploy.sh` looks up each instance's private IP from EC2 by its
`Project` and `Component` tags and passes the values to `docker compose`. This
works the same from your laptop and from a CI job.

`deploy/ec2/.env` holds only secrets and settings (see `env.example`). It is
git-ignored and must be created on each instance that needs it.

## First-time setup

Run from the repo root with AWS credentials for the lab account.

1. **Install Docker and clone the repo** on every instance:
   ```sh
   ./scripts/aws/bootstrap-instances.sh
   ```
2. **Create `/opt/safepay/deploy/ec2/.env`** on `postgres`, `gateway`, `worker`
   (and optionally `monitor` for `GRAFANA_ADMIN_PASSWORD`), based on
   `env.example`. Open a shell with
   `aws ssm start-session --target <instance-id>` and edit the file with `nano`.
   Use the same Postgres values on all three.
3. **Open the required ports** between instances (see below).
4. **Deploy**:
   ```sh
   GIT_REF=main ./scripts/aws/deploy.sh                 # everything, in dependency order
   GIT_REF=main ./scripts/aws/deploy.sh gateway worker  # only some roles
   ```
   `GIT_REF` is the branch or tag instances will check out. The compose files
   must exist on that branch.

## Network ports

Each service needs inbound access from the roles that call it:

| Target | Port | Allowed from |
|--------|------|--------------|
| kafka | 9092 | gateway, worker, monitor |
| postgres | 5432 | gateway, worker |
| redis | 6379 | gateway, worker |
| gateway | 8000 | load, monitor |
| monitor | 3100 | every role, only if you use `WITH_PROMTAIL=1` |

Security groups are managed outside Terraform. Compare them with this table,
especially worker to kafka and gateway to postgres.

## Reaching the UIs

No ports are opened to the internet. Forward a port through SSM instead, for example
Grafana (3000), Prometheus (9090), or AKHQ (8080) on the monitor instance:

```sh
aws ssm start-session --target <monitor-instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3000"],"localPortNumber":["3000"]}'
```

## Notes

- Kafka and Postgres data live in Docker volumes on the instance's root disk and
  are lost if the instance is destroyed.
- Grafana has anonymous access disabled here, unlike the local stack.
- cAdvisor runs only on the monitor instance, and Prometheus scrapes it plus the
  gateway's `/metrics`.
