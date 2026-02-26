# Local Setup Guide with Remote Database

This guide explains how to run the Tesserae V6 application locally on your machine while connecting to the PostgreSQL database hosted on a remote server.

## Prerequisites
1. **Node.js & npm**: For the frontend.
2. **Miniconda/Anaconda**: For managing Python dependencies for the backend.
3. Access to the remote server via SSH (e.g., `<username>@<server-address>`).

## 1. Syncing the Repository
Ensure you have the latest changes from the `main` branch merged into your local branch.
```bash
git fetch origin
git checkout <your-branch-name>
git pull origin main
```
*Note: If you have merge conflicts, resolve them keeping the local setup configuration.*

## 2. Port Forwarding the Database
The remote data resides in a PostgreSQL database on port `5432`. Since this database isn't publicly exposed, you need to create an SSH tunnel to forward it to your local machine.

Open a new terminal window and run:
```bash
ssh -N -L 5433:localhost:5432 <username>@<server-address>
```
*   `-N`: Do not execute a remote command (just forward the port).
*   `-L 5433:localhost:5432`: Forwards your local port `5433` to `localhost:5432` on the remote server.
*   You will be prompted for your SSH password. 
*   **Leave this terminal window open** as long as you are working on the project.

## 3. Configuring Local Environment Variables
In the root directory of the Tesserae V6 project, create or edit the `.env` file to point to your new forwarded port. Replace the database username, password, and secret key with your actual credentials.
```env
DATABASE_URL=postgresql://<db_username>:<db_password>@localhost:5433/<db_name>
SESSION_SECRET=<your-secret-key>
PORT=5001
```
*Note: We use `PORT=5001` because macOS often reserves port `5000` for the AirPlay Receiver plugin.*

## 4. Backend Setup
Create an isolated Python environment using Conda and install the dependencies.

```bash
# Create the environment (only needed once)
conda create -n tesserae python=3.10 -y

# Activate the environment
conda activate tesserae

# Install backend dependencies
pip install -r requirements.txt

# Start the Flask backend server
python main.py
```
*Note: The backend will now start up and listen on `http://localhost:5001`. Keep this terminal running.*

## 5. Frontend Setup
Open a third terminal window for the frontend.

```bash
# Install Node dependencies (only needed once or when package.json changes)
npm install

# Start the Vite development server
npm run dev
```
*Note: This will start the frontend on `http://localhost:5173`. Keep this terminal running.*

## Quick Start Summary
Every time you want to work on the project, you need three terminal windows:
1. **Terminal 1**: SSH Tunnel (`ssh -N -L 5433:localhost:5432 <username>@<server-address>`)
2. **Terminal 2**: Backend (`conda activate tesserae && python main.py`)
3. **Terminal 3**: Frontend (`npm run dev`)
