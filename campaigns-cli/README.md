# campaigns-cli

CLI de pruebas sobre los recursos AWS del flujo de campañas.

Plan: [`plan-campaigns-cli.md`](plan-campaigns-cli.md) · Tasks: [`tasks/`](tasks/README.md)

```bash
cp .env.example .env        # completar credenciales AWS y nombres de recursos
uv sync
uv run campaigns config check
```

> **WSL + OneDrive:** el `.venv` dentro de `/mnt/c` hace todo muy lento (pruebas ~220 s → ~5 s).
> Exporta `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli` (por ejemplo en `~/.bashrc`).
