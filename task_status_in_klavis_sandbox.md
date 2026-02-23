# Toolathlon Task Status in Klavis Sandbox

> **Total tasks:** 108 (from `tasks/finalpool/`)  
> **Supported (MCP servers available):** 52 | **Not supported:** 56  
> **Klavis sandbox ready (can directly run via `toolathlon_task_run_example.py`):** 8

### Klavis Status Legend

| Status | Meaning |
|--------|---------|
| `ready` | Task can be run end-to-end via Klavis sandbox using `toolathlon_task_run_example.py` |
| `pending` | Sandbox is supported but cannot run via `toolathlon_task_run_example.py` |

---

## Supported Tasks

| # | Task Name | MCP Servers | Klavis Status |
|---|-----------|-------------|:------------:|
| 1 | `ab-testing` | google-cloud, filesystem | `pending` |
| 2 | `academic-warning` | google-cloud, excel, filesystem | `pending` |
| 3 | `apply-phd-email` | filesystem, memory, emails, terminal, pdf-tools | `pending` |
| 4 | `arrange-workspace` | filesystem, terminal, pdf-tools, excel | `pending` |
| 5 | `course-assistant` | excel, emails, filesystem, terminal | `pending` |
| 6 | `courses-ta-hws` | terminal, excel, filesystem | **`ready`** |
| 7 | `detect-revised-terms` | filesystem, pdf-tools | **`ready`** |
| 8 | `email-paper-homepage` | emails, github | `pending` |
| 9 | `excel-data-transformation` | excel, filesystem, terminal | `pending` |
| 10 | `excel-market-research` | excel, filesystem, terminal | `pending` |
| 11 | `experiments-recordings` | notion, wandb, terminal, filesystem | `pending` |
| 12 | `filter-low-selling-products` | woocommerce, filesystem, emails | **`ready`** |
| 13 | `flagged-transactions` | google-cloud, excel, terminal, filesystem | `pending` |
| 14 | `game-statistics` | google-cloud, terminal | `pending` |
| 15 | `git-bug-hunt` | git, terminal, filesystem, emails | `ready` |
| 16 | `git-repo` | github, filesystem, pdf-tools | `pending` |
| 17 | `huggingface-upload` | filesystem, terminal, huggingface | `pending` |
| 18 | `imagenet` | filesystem, pdf-tools | `pending` |
| 19 | `interview-report` | filesystem, word | `pending` |
| 20 | `inventory-sync` | woocommerce, filesystem | **`ready`** |
| 21 | `landing-task-reminder` | emails, snowflake, pdf-tools, filesystem | `pending` |
| 22 | `live-transactions` | google-cloud, filesystem | `pending` |
| 23 | `machine-operating` | google-cloud, filesystem, excel | `pending` |
| 24 | `merge-hf-datasets` | huggingface, terminal, filesystem | `pending` |
| 25 | `music-analysis` | excel, google_sheet, terminal | `pending` |
| 26 | `nhl-b2b-analysis` | google_sheet, filesystem, terminal | `pending` |
| 27 | `notion-hr` | filesystem, emails, notion, pdf-tools | `pending` |
| 28 | `notion-personal-website` | filesystem, word, notion | `pending` |
| 29 | `paper-checker` | filesystem, terminal | **`ready`** |
| 30 | `payable-invoice-checker` | emails, pdf-tools, filesystem, snowflake | `pending` |
| 31 | `personal-website-construct` | memory, github | `pending` |
| 32 | `ppt-analysis` | pptx, filesystem, pdf-tools | `pending` |
| 33 | `price-comparison` | filesystem, terminal, pdf-tools, google-cloud | `pending` |
| 34 | `privacy-desensitization` | filesystem, terminal | `pending` |
| 35 | `reimbursement-form-filler` | filesystem, excel, pdf-tools, terminal | `pending` |
| 36 | `sales-accounting` | memory, excel, filesystem | `pending` |
| 37 | `set-conf-cr-ddl` | emails, google_calendar | `pending` |
| 38 | `sla-timeout-monitor` | emails, snowflake, filesystem, pdf-tools, terminal | `pending` |
| 39 | `student-interview` | emails, google_calendar | `pending` |
| 40 | `sync-todo-to-readme` | git, github | **`ready`** |
| 41 | `task-tracker` | github, notion | `pending` |
| 42 | `travel-expense-reimbursement` | emails, snowflake, pdf-tools, filesystem | `pending` |
| 43 | `university-course-selection` | filesystem, pdf-tools, terminal, excel | `pending` |
| 44 | `update-material-inventory` | google_sheet, woocommerce | `pending` |
| 45 | `wandb-best-score` | wandb, filesystem, terminal | `pending` |
| 46 | `wandb-shortest-length` | wandb, filesystem, terminal, excel | `pending` |
| 47 | `woocommerce-customer-survey` | woocommerce, emails, google_forms, filesystem | `ready` |
| 48 | `woocommerce-new-product` | woocommerce, filesystem, emails | **`ready`** |
| 49 | `woocommerce-new-welcome` | woocommerce, filesystem, terminal, google-cloud, emails | `pending` |
| 50 | `woocommerce-product-recall` | woocommerce, emails, google_forms, filesystem | `pending` |
| 51 | `woocommerce-stock-alert` | woocommerce, google_sheet, emails, filesystem | `pending` |
| 52 | `woocommerce-update-cover` | woocommerce | **`ready`** |

---

## Unsupported Tasks

These tasks require MCP servers that are excluded, thus these tasks are not suported.

| # | Task Name | MCP Servers |
|---|-----------|-------------|
| 1 | `academic-pdf-report` | playwright_with_chunk, excel, terminal, arxiv_local, pdf-tools, fetch |
| 2 | `add-bibtex` | scholarly, playwright_with_chunk, filesystem, terminal, fetch |
| 3 | `canvas-arrange-exam` | canvas, emails, memory, terminal |
| 4 | `canvas-art-manager` | filesystem, canvas, terminal, emails |
| 5 | `canvas-art-quiz` | filesystem, canvas, terminal |
| 6 | `canvas-do-quiz` | memory, canvas |
| 7 | `canvas-homework-grader-python` | canvas, filesystem, terminal, emails |
| 8 | `canvas-list-test` | canvas, memory |
| 9 | `canvas-new-students-notification` | filesystem, terminal, canvas |
| 10 | `canvas-submit-late-work` | canvas, memory, filesystem, emails |
| 11 | `cooking-guidance` | filesystem, howtocook |
| 12 | `course-schedule` | filesystem, memory, excel, pdf-tools, fetch |
| 13 | `cvpr-research` | filesystem, fetch, playwright_with_chunk |
| 14 | `dataset-license-issue` | huggingface, github, terminal, fetch |
| 15 | `dietary-health` | filesystem, howtocook, excel, terminal |
| 16 | `fillout-online-forms` | playwright_with_chunk, memory, filesystem |
| 17 | `find-alita-paper` | arxiv_local, filesystem, scholarly |
| 18 | `gdp-cr5-analysis` | google_sheet, playwright_with_chunk, fetch |
| 19 | `git-milestone` | filesystem, terminal, fetch |
| 20 | `hk-top-conf` | filesystem, terminal, playwright_with_chunk, fetch |
| 21 | `identify-all-songs` | filesystem, youtube-transcript, playwright_with_chunk, fetch |
| 22 | `inter-final-performance-analysis` | filesystem, playwright_with_chunk, google_sheet, terminal, fetch |
| 23 | `investment-decision-analysis` | yahoo-finance, google_sheet, excel, filesystem |
| 24 | `invoice-org` | pdf-tools, filesystem, yahoo-finance, excel |
| 25 | `ipad-edu-price` | yahoo-finance, playwright_with_chunk, fetch |
| 26 | `k8s-deployment-cleanup` | k8s, emails, pdf-tools, filesystem |
| 27 | `k8s-mysql` | k8s, filesystem |
| 28 | `k8s-pr-preview-testing` | terminal, filesystem, playwright_with_chunk, k8s |
| 29 | `k8s-redis-helm-upgrade` | k8s, terminal, filesystem |
| 30 | `k8s-safety-audit` | k8s, google_sheet, filesystem |
| 31 | `language-school` | filesystem, playwright_with_chunk, excel, fetch, terminal |
| 32 | `latex-prompt-box` | filesystem, arxiv-latex, terminal |
| 33 | `llm-training-dataset` | playwright_with_chunk, google_sheet, scholarly, fetch |
| 34 | `logical-datasets-collection` | filesystem, scholarly, arxiv_local, pdf-tools, fetch |
| 35 | `meeting-assign` | fetch, emails, playwright_with_chunk, filesystem |
| 36 | `mrbeast-analysis` | youtube, filesystem, excel, youtube-transcript |
| 37 | `notion-find-job` | google_map, notion, emails, playwright_with_chunk |
| 38 | `notion-movies` | playwright_with_chunk, notion, fetch |
| 39 | `nvidia-market` | yahoo-finance, filesystem, terminal, playwright_with_chunk, excel, fetch |
| 40 | `nvidia-stock-analysis` | yahoo-finance, filesystem, terminal, excel |
| 41 | `oil-price` | yahoo-finance, notion, filesystem, terminal |
| 42 | `profile-update-online` | filesystem, playwright_with_chunk, scholarly, arxiv_local, pdf-tools |
| 43 | `quantitative-financial-analysis` | filesystem, yahoo-finance, google_sheet, notion, terminal |
| 44 | `search-ca-school` | filesystem, google_map, playwright_with_chunk, fetch |
| 45 | `shopping-helper` | filesystem, playwright_with_chunk |
| 46 | `stock-build-position` | excel, yahoo-finance, terminal |
| 47 | `subway-planning` | google_map, filesystem, playwright_with_chunk, fetch |
| 48 | `train-ticket-plan` | filesystem, rail_12306, terminal, fetch |
| 49 | `travel-exchange` | terminal, filesystem, yahoo-finance |
| 50 | `trip-adviser` | google_map, fetch, filesystem, playwright_with_chunk |
| 51 | `trip-itinerary-generator` | filesystem, google_map, playwright_with_chunk |
| 52 | `upenn-campus-route` | filesystem, terminal, google_map, fetch |
| 53 | `verl-dataset` | huggingface, filesystem, fetch |
| 54 | `vlm-history-completer` | playwright_with_chunk, google_sheet, arxiv_local, huggingface, fetch |
| 55 | `yahoo-analysis` | yahoo-finance, filesystem, terminal |
| 56 | `youtube-repo` | youtube, youtube-transcript, filesystem, fetch, github |

---
