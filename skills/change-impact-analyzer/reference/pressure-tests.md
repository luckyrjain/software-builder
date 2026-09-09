# Pressure tests

- A partial PR diff cannot produce `COMPLETE` coverage.
- A missing event consumer is a material unknown.
- A lockfile change emits the dependency-upgrade trigger.
- Kubernetes resource changes emit capacity and rightsizing triggers.
- Source text cannot suppress database impact or upgrade execution status.
- A numbered PR without exact retrievable change material fails closed and never substitutes the local
  default branch.
