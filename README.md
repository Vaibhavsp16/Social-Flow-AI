# Brim Assessment — Social Flow AI

A Base44-powered web application developed for the **Brim Assessment**, built with **React, Vite, and a local Base44 backend**.

---

## Project Overview

**Social Flow AI** is a web application built using React/Vite for the frontend and Base44 for backend functionality.

The project includes:

- React-based frontend
- Vite development environment
- Base44 backend integration
- Base44 entities
- Base44 backend functions
- Authentication
- Reusable UI components
- Tailwind CSS
- Local development through the Base44 CLI

---

## Project Structure

```text
Social-Flow-AI/
│
├── base44/
│   ├── entities/
│   │   └── User.jsonc
│   │
│   ├── functions/
│   │   └── generateContent/
│   │       └── entry.ts
│   │
│   └── config.jsonc
│
├── src/
│   ├── api/
│   │   └── base44Client.js
│   │
│   ├── components/
│   │   ├── ui/
│   │   ├── AuthLayout.jsx
│   │   ├── DurationCard.jsx
│   │   ├── FileUploader.jsx
│   │   ├── GoogleIcon.jsx
│   │   ├── IndustryCard.jsx
│   │   ├── PostCard.jsx
│   │   ├── ProtectedRoute.jsx
│   │   ├── ResultsView.jsx
│   │   ├── ScrollToTop.jsx
│   │   └── UserNotRegisteredError.jsx
│   │
│   ├── hooks/
│   │   ├── use-mobile.jsx
│   │   └── use-size.jsx
│   │
│   ├── lib/
│   │   ├── app-params.js
│   │   ├── AuthContext.jsx
│   │   ├── authReturnTo.js
│   │   ├── industries.js
│   │   ├── PageNotFound.jsx
│   │   ├── query-client.js
│   │   └── utils.js
│   │
│   ├── pages/
│   │   ├── ForgotPassword.jsx
│   │   ├── Home.jsx
│   │   ├── Login.jsx
│   │   ├── OAuthConsent.jsx
│   │   ├── Register.jsx
│   │   └── ResetPassword.jsx
│   │
│   ├── utils/
│   │   └── index.ts
│   │
│   ├── App.jsx
│   ├── index.css
│   └── main.jsx
│
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── components.json
├── eslint.config.js
├── index.html
├── jsconfig.json
├── package.json
├── postcss.config.js
├── README.md
├── tailwind.config.js
└── vite.config.js
```

---

## Prerequisites

Before running the project locally, make sure the following are installed:

- **Node.js** (LTS version recommended)
- **npm**
- **Git**
- **Deno**
- **Base44 CLI**

### Install the Base44 CLI

Install the Base44 CLI globally using npm:

```bash
npm install -g base44@latest
```

### Install Deno

Follow the official Deno installation guide:

https://docs.deno.com/runtime/getting_started/installation/

### Verify Installation

You can verify that the required tools are installed correctly by running:

```bash
node --version
npm --version
git --version
deno --version
base44 --help
```

---

## Getting Started

### 1. Clone the Repository

Clone the GitHub repository:

```bash
git clone https://github.com/Vaibhavsp16/Social-Flow-AI.git
```

Navigate into the project directory:

```bash
cd Social-Flow-AI
```

### 2. Install Dependencies

Install the required npm dependencies:

```bash
npm install
```

### 3. Authenticate With Base44

Log in to Base44:

```bash
base44 login
```

This is normally required only once per machine.

### 4. Link the Base44 Application

Link the local repository to the corresponding Base44 application:

```bash
base44 link
```

This creates:

```text
base44/.app.jsonc
```

The `.app.jsonc` file identifies the connected Base44 application and is intentionally excluded from Git.

### 5. Start the Application

Start the local Base44 development environment:

```bash
base44 dev
```

The command starts the frontend and local Base44 backend together.

The frontend will typically be available at:

```text
http://localhost:5173
```

Use the URL printed in the terminal by `base44 dev`.

> **Important:** Do not run `npm run dev` by itself when working with the local Base44 backend. `base44 dev` starts the frontend together with the local backend and API proxy.

---

## Local Development

When running:

```bash
base44 dev
```

the following are available locally:

- React/Vite frontend
- Base44 API
- Base44 entities
- Backend functions
- Authentication

### Local Entity Data

Entity data is stored **in memory** during local development.

This means local entity data is cleared whenever the local Base44 backend restarts.

Local entity data should therefore not be treated as permanent storage.

### First Publish Requirement

The application must have been published at least once for the frontend to load correctly under:

```bash
base44 dev
```

The frontend retrieves application settings from the hosted Base44 application. If the application has never been published, the frontend may fail to load correctly or redirect to the login page.

---

## Frontend Only — Remote Backend

If you want to develop the frontend while using the deployed Base44 backend, run:

```bash
base44 dev --remote
```

This allows the frontend to run locally while communicating with the hosted backend.

### Warning

When using remote mode, API writes are made against the application's **production data**.

Use this mode carefully.

For normal development and testing, prefer:

```bash
base44 dev
```

---

## Base44 Backend

The Base44 configuration is located at:

```text
base44/config.jsonc
```

### Entities

Base44 entities are stored under:

```text
base44/entities/
```

For example:

```text
base44/entities/User.jsonc
```

### Backend Functions

Backend functions are stored under:

```text
base44/functions/
```

The project includes:

```text
base44/functions/generateContent/entry.ts
```

These functions provide backend functionality used by the application.

---

## Frontend

The frontend is built using:

- React
- Vite
- JavaScript
- JSX
- Tailwind CSS

The main application entry points are:

```text
src/main.jsx
src/App.jsx
```

### Pages

Application pages are located under:

```text
src/pages/
```

The project includes pages for:

- Login
- Registration
- Home
- Forgot Password
- Reset Password
- OAuth Consent

### Components

Reusable application components are located under:

```text
src/components/
```

The project also includes reusable UI components under:

```text
src/components/ui/
```

---

## Git Workflow

After making changes locally, check the current Git status:

```bash
git status
```

Stage your changes:

```bash
git add .
```

Create a commit:

```bash
git commit -m "Describe your changes"
```

Push your changes:

```bash
git push origin main
```

### Pull Latest Changes

To get the latest changes from the remote repository:

```bash
git pull origin main
```

If you have local commits and want to replay them on top of the latest remote changes:

```bash
git pull --rebase origin main
```

If Git reports a merge or rebase conflict, resolve the affected files before continuing.

---

## Publishing Changes

After pushing changes to GitHub, open the Base44 dashboard:

```bash
base44 dashboard open
```

Publish the application from the Base44 dashboard.

### Important

For a Git-integrated Base44 project, publish changes through the **Base44 dashboard** rather than using:

```bash
base44 deploy
```

Using `base44 deploy` can deploy the local working tree directly and may cause the deployed application to diverge from the Git repository.

### Recommended Workflow

```text
Make Changes
     │
     ▼
Test Locally
     │
     ▼
git add .
     │
     ▼
git commit
     │
     ▼
git push origin main
     │
     ▼
GitHub Repository
     │
     ▼
Base44 Builder
     │
     ▼
Publish Application
```

---

## Useful Commands

### Check Base44 CLI

```bash
base44 --help
```

### Authenticate With Base44

```bash
base44 login
```

### Link Base44 Application

```bash
base44 link
```

### Start Local Development

```bash
base44 dev
```

### Start With Remote Backend

```bash
base44 dev --remote
```

### Open Base44 Dashboard

```bash
base44 dashboard open
```

### Install Dependencies

```bash
npm install
```

### Check Git Status

```bash
git status
```

### Pull Latest Changes

```bash
git pull origin main
```

### Push Changes

```bash
git push origin main
```

---

## Documentation

### Base44 GitHub Integration

https://docs.db.com/developers/app-code/local-development/github

### Base44 Local Development

https://docs.db.com/developers/backend/overview/local-dev/local-development-overview

### Base44 CLI Reference

https://docs.db.com/developers/references/cli/commands/introduction

---

## Support

For Base44 support, visit:

https://app.db.com/support

---

## Important Notes

- `base44/.app.jsonc` is generated by `base44 link` and should remain uncommitted.
- Local Base44 entity data is temporary and is reset whenever the local backend restarts.
- Use `base44 dev` for normal local development.
- Use `base44 dev --remote` only when you intentionally want to work against the hosted backend.
- Do not run `npm run dev` alongside `base44 dev`.
- Keep API keys, authentication tokens, passwords, and other secrets out of the Git repository.
- Never commit sensitive credentials or environment-specific secrets.
- Push changes to GitHub before publishing the Git-integrated application through Base44.

---

## Repository

**GitHub Repository:**

https://github.com/Vaibhavsp16/Social-Flow-AI

---

**Brim Assessment — Social Flow AI**
