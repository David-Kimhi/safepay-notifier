locals {
  instances = {
    kafka = {
      instance_type       = "m6i.large"
      root_volume_size_gb = 30
    }
    postgres = {
      instance_type       = "m6i.xlarge"
      root_volume_size_gb = 30
    }
    redis = {
      instance_type       = "m6i.large"
      root_volume_size_gb = 16
    }
    gateway = {
      instance_type       = "c6i.large"
      root_volume_size_gb = 20
    }
    worker = {
      instance_type       = "c6i.large"
      root_volume_size_gb = 20
    }
    load = {
      instance_type       = "c6i.large"
      root_volume_size_gb = 20
    }
    monitor = {
      instance_type       = "c6i.large"
      root_volume_size_gb = 30
    }
  }
}

resource "aws_instance" "lab" {
  for_each = local.instances

  ami                         = var.ami_id
  instance_type               = each.value.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids[each.key]
  iam_instance_profile        = var.iam_instance_profile_name
  associate_public_ip_address = true

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = each.value.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true
  }

  volume_tags = {
    Name      = "safepay-lab-${each.key}-root"
    Component = each.key
  }

  tags = {
    Name      = "safepay-lab-${each.key}"
    Component = each.key
  }
}

# Controls power state only. Instances are always launched running, so with
# "stopped" they are created and then stopped right after.
resource "aws_ec2_instance_state" "lab" {
  for_each = aws_instance.lab

  instance_id = each.value.id
  state       = var.instances_state
}