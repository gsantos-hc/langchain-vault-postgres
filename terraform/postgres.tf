# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MIT

# PostgreSQL Database ------------------------------------------------------------------
resource "kubernetes_service_v1" "psql" {
  metadata {
    name      = local.db_svc_name
    namespace = var.kube_namespace
    labels    = local.db_labels
  }

  spec {
    type     = "ClusterIP"
    selector = local.db_labels

    port {
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_stateful_set_v1" "psql" {
  metadata {
    name      = local.db_svc_name
    namespace = var.kube_namespace
    labels    = local.db_labels
  }

  spec {
    service_name = local.db_svc_name
    replicas     = 1

    volume_claim_template {
      metadata {
        name = "data"
      }

      spec {
        access_modes = ["ReadWriteOnce"]
        resources {
          requests = {
            storage = "1Gi"
          }
        }
      }
    }

    selector {
      match_labels = local.db_labels
    }

    template {
      metadata {
        labels = local.db_labels
      }

      spec {
        container {
          name              = local.db_svc_name
          image             = "${var.db_image_name}:${var.db_image_tag}"
          image_pull_policy = "IfNotPresent"

          volume_mount {
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }

          env {
            name  = "POSTGRES_PASSWORD"
            value = var.db_default_password
          }
        }
      }
    }
  }
}
