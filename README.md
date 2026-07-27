# KNPU FPEI Research System

Research System for **FPEI** at **Korea National Police University**.

---

## MANAGER

<img src="homepage/server/app/public/assets/imgs/systems/manager.png" alt="Manager Service" width="700">
[**Open**](https://manager.knpu.re.kr)

---

## CRAWLER

<img src="homepage/server/app/public/assets/imgs/systems/crawler.png" alt="Crawler Service" width="700">
[**Open**](https://crawler.knpu.re.kr)

---

## NETWORK

<img src="homepage/server/app/public/assets/imgs/systems/network.png" alt="Network Service" width="700">
[**Open**](https://network.knpu.re.kr)

---

## STATISTICS

<img src="homepage/server/app/public/assets/imgs/systems/statistics.png" alt="Statistics Service" width="700">
[**Open**](https://statistics.knpu.re.kr)

---

## KEMKIM

<img src="homepage/server/app/public/assets/imgs/systems/kemkim.png" alt="Kemkim Service" width="700">
[**Open**](https://kemkim.knpu.re.kr)

---

## Lab LLM

<img src="homepage/server/app/public/assets/imgs/systems/labllm.png" alt="Lab LLM Service" width="700">
[**Open**](https://llm.knpu.re.kr)

---

## AI Legal Complaint Generation Service

<img src="homepage/server/app/public/assets/imgs/systems/complaint.png" alt="Legal Service" width="700">
[**Open**](https://complaint.knpu.re.kr)

---

## LecAI

<img src="homepage/server/app/public/assets/imgs/systems/lecai.png" alt="LecAI Service" width="700">
[**Open**](https://lec.knpu.re.kr)

---

## Development & Operations

This system manages dependencies independently for each service. Each subdirectory contains its own project configuration. To develop or run a specific service, navigate to its directory and set up a dedicated virtual environment (`.venv`).

### Isolated Dependency Synchronization (Standalone Environment)
Instead of sharing a single virtual environment across the entire repository, you should navigate to the specific service directory you are working on and synchronize its dependencies independently.

```bash
# Example 1: Set up and sync the homepage system standalone
cd homepage
uv sync

# Example 2: Set up and sync the admin system standalone
cd admin
uv sync

# Example 3: Set up and sync the crawler system standalone
cd crawler
uv sync
```
    
---
© 2026 **FPEI**. All rights reserved.
Developed by [**Yojun Moon**](https://github.com/yojun313)