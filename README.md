# LangChain + HashiCorp Vault

Sample LangChain app that enables natural language querying of a PostgreSQL database, with HashiCorp Vault generating short-lived database credentials tied to each individual user session for traceability.

## Requirements

1. Running Vault cluster
2. Vault Agent Sidecar Injector deployed on Kubernetes cluster
3. PostgreSQL server that is reachable by Vault
4. OpenAI API Key stored in a Vault KV secret as `{"api_key": "key_here"}`

## Acknowledgements

This repository draws heavily on work by [Gary Stafford](https://github.com/aws-solutions-library-samples/guidance-for-natural-language-queries-of-relational-databases-on-aws). The sample data set is from the Museum of Modern Art's collection, available on [GitHub](https://github.com/MuseumofModernArt/collection).
