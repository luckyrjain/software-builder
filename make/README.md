# Make includes

The root `Makefile` remains the public entry point. Large legacy target definitions live in `core.mk`; the root file contains repository-wide phony declarations and includes the core target set.
