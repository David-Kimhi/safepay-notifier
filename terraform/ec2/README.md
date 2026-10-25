# SafePay EC2 lab

This configuration manages only the seven EC2 instances. The VPC, subnet,
security groups, IAM role, and instance profile must already exist. Terraform
receives their IDs or name as inputs and will not modify or destroy them.

The instances use public IPs for outbound access from the existing public
subnet, but their security groups should allow inbound traffic only from the
appropriate lab security groups. Connect with Systems Manager Session Manager;
no SSH key is configured. The supplied instance profile must include
`AmazonSSMManagedInstanceCore` permissions.

## Prepare

1. Install Terraform 1.5 or newer and configure AWS credentials with the AWS
   CLI or IAM Identity Center. Do not put AWS access keys in this directory.
2. Copy `terraform.tfvars.example` to `terraform.tfvars` and replace the sample
   AMI, subnet, instance profile, and security group IDs with your real values.
3. Confirm that the AMI is Ubuntu Server 24.04 LTS x86-64 in the selected region,
   and that the instance profile exists (EC2 attaches an instance profile, not a
   bare IAM role).

## Preview and launch

From this directory, run:

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan
```

`plan` previews the proposed instances and does not launch them. Review its
output carefully. Run `terraform apply` only when you are ready to launch and
begin incurring charges. Terraform writes private and public IPs after apply;
use the private IPs for service connections.

## Tear down

Run `terraform destroy` to terminate only the EC2 instances managed by this
configuration. Their root EBS volumes are configured for deletion on
termination. Back up anything you need first. Existing networking, security
groups, IAM resources, and any unrelated resources are outside this Terraform
state and will not be destroyed.

The seven root volumes total 166 GiB. The EBS free-tier notice is an allowance,
not a per-volume size limit; storage beyond applicable offers/credits can be
billed even while instances are stopped.