variable "aws_region" {
  description = "AWS region where the existing subnet and lab resources are located."
  type        = string
}

variable "ami_id" {
  description = "Ubuntu Server 24.04 LTS x86-64 AMI ID for aws_region."
  type        = string
}

variable "subnet_id" {
  description = "ID of the existing public subnet in the lab VPC."
  type        = string
}

variable "iam_instance_profile_name" {
  description = "Name of the existing EC2 instance profile with Systems Manager permissions."
  type        = string
}

variable "security_group_ids" {
  description = "Existing security group IDs, keyed by instance role."
  type        = map(list(string))

  validation {
    condition = alltrue([
      for role in ["kafka", "postgres", "redis", "gateway", "worker", "load", "monitor"] :
      try(length(var.security_group_ids[role]) > 0, false)
    ])
    error_message = "Provide at least one existing security group ID for each role: kafka, postgres, redis, gateway, worker, load, and monitor."
  }
}