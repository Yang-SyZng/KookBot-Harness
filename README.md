# KookBot Harness

![version](https://img.shields.io/badge/version-0.0.1__alpha.1-blue)
![GitHub last commit](https://img.shields.io/github/last-commit/Yang-SyZng/KookBot-Harness?logo=github)
![github stars](https://img.shields.io/github/stars/Yang-SyZng/KookBot-Harness?style=social)

This is a KookBot Agent.

## Config

```bash
cp .env.example .env
```

In `.env`, fill in the new `KOOK_TOKEN`, `API_KEY`, `BASE_URL`, and `LLM_MODEL_ID`.

## Run

```bash
.venv/bin/python examples/get.py
```

Only messages explicitly marked with `@Bot` are processed. Attachment input in the first version only supports single files within a card; readable file formats are `.txt`, `.md`, `.json`, and `.csv`.

## Test

```bash
.venv/bin/python -m unittest discover -s tests -v
```
