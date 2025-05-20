variable "kube_namespace" {
  description = "Name of the Kubernetes namespace in which to deploy the demo resources."
  type        = string
  default     = "langchain-vault-demo"
}

variable "image_name" {
  description = "Name of the container image with the demo application."
  type        = string
  default     = "langchain-vault-demo"
}

variable "image_tag" {
  description = "Demo application container image tag."
  type        = string
  default     = "latest"
}

variable "db_image_name" {
  description = "Name of the container image with the database."
  type        = string
  default     = "langchain-vault-demo-psql"
}

variable "db_image_tag" {
  description = "Database container image tag."
  type        = string
  default     = "latest"
}

variable "db_default_password" {
  description = "Default password for the database."
  type        = string
  sensitive   = true
  default     = "securePassword"
}

variable "vault_addr" {
  description = "Vault cluster address."
  type        = string
}

variable "vault_k8s_auth_backend" {
  description = "Name of the Kubernetes authentication backend in Vault."
  type        = string
  default     = "kubernetes"
}

variable "vault_k8s_auth_role" {
  description = "Name of the Kubernetes authentication role in Vault."
  type        = string
  default     = "langchain-vault-demo"
}

variable "vault_policy_name" {
  description = "Name of the Vault policy."
  type        = string
  default     = "langchain-vault-demo"
}

variable "vault_db_mount" {
  description = "Name of the database secret backend in Vault."
  type        = string
  default     = "database"
}

variable "vault_db_role" {
  description = "Name of the database role in Vault."
  type        = string
  default     = "langchain-vault-demo"
}

variable "vault_db_name" {
  description = "Name of the database in Vault."
  type        = string
}

variable "vault_openai_key_path" {
  description = "API path to the OpenAI API Key in Vault."
  type        = string
}
