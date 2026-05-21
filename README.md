# KNPU PAILAB Research System

Research System for **PAILAB** at **Korea National Police University**.

---

## MANAGER
> An integrated platform supporting research resource management and big data analysis.

![Manager Service](homepage/app/public/assets/imgs/systems/manager.png)
[**Open**](https://knpu.re.kr/manager)

---

## CRAWLER
> Builds datasets through large-scale data collection.

![Crawler Service](homepage/app/public/assets/imgs/systems/crawler.png)
[**Open**](https://crawler.knpu.re.kr)

---

## AI Legal Complaint Generation Service
> A service that assists in generating draft legal complaints meeting legal requirements using LLMs.

![Legal Service](homepage/app/public/assets/imgs/systems/complaint.png)
[**Open**](https://complaint.knpu.re.kr)

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
© 2026 **PAILAB**. All rights reserved.
Developed by [**Yojun Moon**](https://github.com/yojun313)