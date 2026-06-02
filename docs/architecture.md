# Architecture Notes

This project is the clean-room runtime rebuild of the earlier `salva` exploration project.

Key choices:

- standalone service before skillization
- deterministic pipeline first
- canonical internal schema plus caller-specific transforms
- local OMLx model provider as the default LLM path
- layered storage and backup
- user-experience profile resolver for task-oriented presets

Use the root `README.md` for the product-level architecture and `TODO.md` for phased execution.
