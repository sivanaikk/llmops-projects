output "cluster_name" {
  value = module.eks.cluster_name
}

output "configure_kubectl" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "karpenter_node_role" {
  value = module.karpenter.node_iam_role_name
}

output "gateway_secret_arn" {
  value = aws_secretsmanager_secret.gateway.arn
}
