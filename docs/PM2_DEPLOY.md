# PM2 Remote Deployment Guide

This project supports PM2 remote deployments without Docker.

## Requirements
- Remote host reachable via SSH
- Git repo access on remote (SSH key or deploy key)
- Node.js + PM2 installed on remote
- Python 3 + pip + venv on remote

## Configure `ecosystem.config.js`
Edit placeholders under `deploy.production`:
- `user`: SSH user (e.g., `ubuntu`)
- `host`: array with hostname or IP
- `repo`: SSH URL (e.g., `git@github.com:org/repo.git`)
- `path`: deploy path on remote (e.g., `/var/www/inference-node`)
- `env`: production env vars (`JWT_SECRET`, etc.)

## First-time Setup
On your local machine (with SSH agent forwarding):
```bash
# Install PM2 locally if not present
npm install -g pm2

# Create remote directories and clone on first deploy
pm2 deploy services/inference-node/ecosystem.config.js production setup
```

## Deploy
```bash
# From repo root
pm2 deploy services/inference-node/ecosystem.config.js production
```
This runs `post-deploy`: `pm2 startOrReload services/inference-node/ecosystem.config.js --env production` on the remote.

## Remote Prereqs (run once)
On the remote host:
```bash
# Node.js / PM2
npm install -g pm2

# Python
sudo apt update
sudo apt install -y python3-pip python3-venv
```
PM2 will execute `./bin/serve.sh` under the app directory, which creates a venv and installs `requirements.txt` before starting `uvicorn`.

## Notes
- Logs are directed to `/dev/null` to avoid PHI persistence; use `pm2 logs inference-node` for ephemeral viewing.
- Provide production secrets via `env_production` in `ecosystem.config.js` or host-level environment management.
- For multiple nodes, run PM2 deploy to each host (list hosts in the config) and manage via AWS scheduler.

## Troubleshooting
- Exit code 127 locally when running `pm2` commands typically means the command is missing:
	- Install PM2: `npm install -g pm2`
	- If `npm` is missing, install Node.js and npm: `sudo apt install -y nodejs npm`
- `pip` or `venv` missing on remote during `post-deploy`:
	- Install: `sudo apt install -y python3-pip python3-venv`
- SSH issues during deploy:
	- Ensure SSH agent forwarding and keys: `ssh -A user@host`
	- Verify repo access: `ssh -T git@github.com`
