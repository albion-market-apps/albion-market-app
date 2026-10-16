# Contribuindo

## Fluxo

1. Crie uma branch a partir de `main`: `feat/...`, `fix/...`, `chore/...`.
2. Commits no padrão [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`.
3. Rode `make fmt` e `make test` antes de abrir PR.
4. Abra PR contra `main`; o CI precisa passar (lint + testes de cada pacote).

## Setup local

Veja [README.md](README.md) para o passo a passo de `make dev` / `make migrate` / `make seed`.

## Padrões de código

- **Python**: `ruff` (lint + format) e `mypy`. Rodado via `pre-commit`.
- **Web**: ESLint + Prettier, TypeScript strict.
- **Flutter**: `flutter format` + `flutter analyze` com `analysis_options.yaml` estrito.

## Commits e versionamento

Usamos Conventional Commits + Commitlint (validado no CI) e Semantic Versioning
para releases do backend/worker (tags `vX.Y.Z`).
