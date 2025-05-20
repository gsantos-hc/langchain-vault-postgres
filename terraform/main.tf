# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MIT

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.36.0"
    }

    vault = {
      source  = "hashicorp/vault"
      version = ">= 4.8.0"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

locals {
  app_name = "vault-nlq-demo"
  common_labels = {
    "app.kubernetes.io/part-of" = local.app_name
  }

  deployment_labels = merge(local.common_labels, {
    "app.kubernetes.io/component" = "app"
    "app.kubernetes.io/name"      = local.app_name
  })

  db_svc_name = "moma-collection"
  db_labels = merge(local.common_labels, {
    "app.kubernetes.io/component" = "database"
    "app.kubernetes.io/name"      = "postgresql"
  })
}

resource "kubernetes_service_v1" "vault_nlq_demo" {
  metadata {
    name      = local.app_name
    namespace = var.kube_namespace
    labels    = local.common_labels
  }

  spec {
    type     = "ClusterIP"
    selector = local.deployment_labels
    port {
      port        = 80
      target_port = 8501
    }
  }
}

resource "kubernetes_deployment_v1" "vault_nlq_demo" {
  metadata {
    name      = local.app_name
    namespace = var.kube_namespace
    labels    = local.common_labels
  }

  spec {
    replicas = 1

    selector {
      match_labels = local.deployment_labels
    }

    template {
      metadata {
        labels = merge(local.deployment_labels, { "app.kubernetes.io/version" = var.image_tag })
        annotations = {
          "vault.hashicorp.com/agent-inject"             = "true"
          "vault.hashicorp.com/agent-inject-containers"  = "nlq-app"
          "vault.hashicorp.com/agent-inject-token"       = "true"
          "vault.hashicorp.com/agent-revoke-on-shutdown" = "true"
          "vault.hashicorp.com/role"                     = vault_kubernetes_auth_backend_role.vault_nlq_demo.role_name

          # OpenAI API Key
          "vault.hashicorp.com/agent-inject-secret-openai-token"   = var.vault_openai_key_path
          "vault.hashicorp.com/agent-inject-template-openai-token" = <<EOT
            {{- with secret "${var.vault_openai_key_path}" -}}
              {{- .Data.data.api_key }}
            {{- end -}}
          EOT
        }
      }

      spec {
        container {
          name              = "nlq-app"
          image             = "${var.image_name}:${var.image_tag}"
          image_pull_policy = "IfNotPresent"

          readiness_probe {
            http_get {
              path = "/healthz"
              port = 8501
            }
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
          }

          env {
            name  = "VAULT_ADDR"
            value = var.vault_addr
          }

          env {
            name  = "VAULT_DB_MOUNT"
            value = var.vault_db_mount
          }

          env {
            name  = "VAULT_DB_ROLE"
            value = vault_database_secret_backend_role.vault_nlq_demo.name
          }

          env {
            name  = "DB_HOST"
            value = "${kubernetes_service_v1.psql.metadata[0].name}:${kubernetes_service_v1.psql.spec[0].port[0].port}"
          }

          env {
            name  = "DB_NAME"
            value = "moma"
          }
        }
      }
    }
  }
}
