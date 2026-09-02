# Daily Learning Planner (DLP)

Daily Learning Planner is a collaborative, AI-enhanced educational platform designed to provide students with learning clarity and actionable progress.

## Repository Architecture

This repository is structured as a monorepo containing three core services designed to be deployed as separate services:

* **`backend-django/`**: Core platform API powered by Django and Django REST Framework. Manages authentication, users, classrooms, courses, progress tracking, assignments, and quizzes.
* **`backend-fastapi/`**: Asynchronous AI & real-time service powered by FastAPI. Manages WebSockets, RAG (Retrieval-Augmented Generation) document pipelines, pgvector similarity searches, and MCP (Model Context Protocol) integration *(scaffolded in a later phase)*.
* **`frontend/`**: Client application built with React, TypeScript, TanStack Query, and Tailwind CSS.

## Getting Started

Refer to the README documentation inside each individual service directory for service-specific setup and run instructions.

## Documentation & Interview Learning Logs

* [01. Project Scaffolding & Setup Guide](file:///c:/Users/balaj/Desktop/DLP/docs/01_project_scaffolding_and_setup.md): Complete breakdown of commands, dependencies, architecture choices, and interview Q&A for Phase 0 setup.
* [02. Custom User Model & Auth Guide](file:///c:/Users/balaj/Desktop/DLP/docs/02_custom_user_model_and_auth.md): Step-by-step guide for creating a custom User model extending AbstractUser with email login and roles.
* [03. Classrooms App & Authorization Guide](file:///c:/Users/balaj/Desktop/DLP/docs/03_classrooms_app_and_authorization.md): Deep dive into Classroom models, automatic memberships, DB unique constraints, and security visibility scoping.
* [04. Study Groups App & Phase 1 Completion Guide](file:///c:/Users/balaj/Desktop/DLP/docs/04_study_groups_app_and_phase1_completion.md): Guide to student study groups, soft leaving state machines, member management, and complete Phase 1 backend overview.
* [05. Frontend Auth & API Client Guide](file:///c:/Users/balaj/Desktop/DLP/docs/05_frontend_auth_and_api_client.md): Architectural guide for typed Axios API client, JWT request/response interceptors, automatic 401 token refresh, and AuthContext.
* [06. Classroom & Group Screens Guide](file:///c:/Users/balaj/Desktop/DLP/docs/06_classroom_and_group_screens.md): Complete guide to TanStack Query data fetching, role-based UI access control, join links, and group management screens.






