resource "vault_kubernetes_auth_backend_role" "vault_nlq_demo" {
  backend                          = var.vault_k8s_auth_backend
  role_name                        = var.vault_k8s_auth_role
  bound_service_account_names      = ["default"]
  bound_service_account_namespaces = [var.kube_namespace]
  token_policies                   = [var.vault_policy_name]
  token_ttl                        = 3600
}

resource "vault_policy" "vault_nlq_demo" {
  name   = var.vault_policy_name
  policy = data.vault_policy_document.vault_nlq_demo.hcl
}

data "vault_policy_document" "vault_nlq_demo" {
  rule {
    description  = "Generate read-only credentials for the database"
    path         = "${var.vault_db_mount}/creds/${var.vault_db_role}"
    capabilities = ["read"]
  }
}

resource "vault_database_secret_backend_role" "vault_nlq_demo" {
  backend     = var.vault_db_mount
  name        = var.vault_db_role
  db_name     = vault_database_secret_backend_connection.moma_collection.name
  default_ttl = 300
  max_ttl     = 3600 * 24

  creation_statements = [
    "BEGIN;",
    "CREATE ROLE \"{{username}}\" LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT USAGE ON SCHEMA public TO \"{{username}}\";",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{username}}\";",
    "COMMIT;",
  ]

  renew_statements = [
    "ALTER ROLE \"{{username}}\" VALID UNTIL '{{expiration}}';",
  ]

  revocation_statements = [
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = '{{username}}' AND pid <> pg_backend_pid();",
    "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM \"{{username}}\";",
    "REVOKE ALL PRIVILEGES ON SCHEMA public FROM \"{{username}}\";",
    "DROP OWNED BY \"{{username}}\";",
    "DROP ROLE \"{{username}}\";",
  ]
}

resource "vault_database_secret_backend_connection" "moma_collection" {
  backend       = var.vault_db_mount
  name          = var.vault_db_name
  allowed_roles = [var.vault_db_role]

  postgresql {
    connection_url = "postgresql://{{username}}:{{password}}@${kubernetes_stateful_set_v1.psql.metadata[0].name}.${var.kube_namespace}.svc.cluster.local:5432/moma?sslmode=disable"
    username       = "postgres"
    password       = var.db_default_password
  }

  lifecycle {
    ignore_changes = [postgresql[0].password]
  }

  depends_on = [
    kubernetes_stateful_set_v1.psql,
    kubernetes_service_v1.psql,
  ]
}
