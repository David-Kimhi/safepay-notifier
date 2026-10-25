output "instance_ids" {
  description = "EC2 instance IDs, keyed by service role."
  value       = { for role, instance in aws_instance.lab : role => instance.id }
}

output "private_ips" {
  description = "Private IP addresses for configuring service-to-service connections."
  value       = { for role, instance in aws_instance.lab : role => instance.private_ip }
}

output "public_ips" {
  description = "Public IP addresses; access instances through Systems Manager rather than SSH."
  value       = { for role, instance in aws_instance.lab : role => instance.public_ip }
}