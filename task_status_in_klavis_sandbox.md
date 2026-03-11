# Toolathlon Task Status in Klavis Sandbox

> **Total tasks:** 108 (from `tasks/finalpool/`)  
> **Supported (MCP servers available):** 75 | **Not supported:** 33

### Klavis Status Legend

| Status | Meaning |
|--------|---------|
| `ready` | Task can be run end-to-end via Klavis sandbox using `toolathlon_task_run_example.py` |
| `pending` | Sandbox is supported but cannot run via `toolathlon_task_run_example.py` |

---

## Supported Tasks

| # | Task Name | MCP Servers | Klavis Status |
|---|-----------|-------------|:------------:|
| 1 | `ab-testing` | google-cloud, filesystem | `ready` |
| 2 | `academic-pdf-report` | playwright_with_chunk, excel, terminal, arxiv_local, pdf-tools, fetch | `pending` |
| 3 | `academic-warning` | google-cloud, excel, filesystem | `ready` |
| 4 | `apply-phd-email` | filesystem, memory, emails, terminal, pdf-tools | `ready` |
| 5 | `arrange-workspace` | filesystem, terminal, pdf-tools, excel | `ready` |
| 6 | `canvas-arrange-exam` | canvas, emails, memory, terminal | `pending` |
| 7 | `canvas-art-manager` | filesystem, canvas, terminal, emails | `pending` |
| 8 | `canvas-art-quiz` | filesystem, canvas, terminal | `pending` |
| 9 | `canvas-do-quiz` | memory, canvas | `pending` |
| 10 | `canvas-homework-grader-python` | canvas, filesystem, terminal, emails | `pending` |
| 11 | `canvas-list-test` | canvas, memory | `pending` |
| 12 | `canvas-new-students-notification` | filesystem, terminal, canvas | `pending` |
| 13 | `canvas-submit-late-work` | canvas, memory, filesystem, emails | `pending` |
| 14 | `course-assistant` | excel, emails, filesystem, terminal | `ready` |
| 15 | `course-schedule` | filesystem, memory, excel, pdf-tools, fetch | `pending` |
| 16 | `courses-ta-hws` | terminal, excel, filesystem | `ready` |
| 17 | `cvpr-research` | filesystem, fetch, playwright_with_chunk | `pending` |
| 18 | `dataset-license-issue` | huggingface, github, terminal, fetch | `pending` |
| 19 | `detect-revised-terms` | filesystem, pdf-tools | `ready` |
| 20 | `email-paper-homepage` | emails, github | `ready` |
| 21 | `excel-data-transformation` | excel, filesystem, terminal | `ready` |
| 22 | `excel-market-research` | excel, filesystem, terminal | `ready` |
| 23 | `experiments-recordings` | notion, wandb, terminal, filesystem | `ready` |
| 24 | `fillout-online-forms` | playwright_with_chunk, memory, filesystem | `pending` |
| 25 | `filter-low-selling-products` | woocommerce, filesystem, emails | `ready` |
| 26 | `flagged-transactions` | google-cloud, excel, terminal, filesystem | `ready` |
| 27 | `game-statistics` | google-cloud, terminal | `ready` |
| 28 | `gdp-cr5-analysis` | google_sheet, playwright_with_chunk, fetch | `pending` |
| 29 | `git-bug-hunt` | git, terminal, filesystem, emails | `ready` |
| 30 | `git-milestone` | filesystem, terminal, fetch | `pending` |
| 31 | `git-repo` | github, filesystem, pdf-tools | `ready` |
| 32 | `hk-top-conf` | filesystem, terminal, playwright_with_chunk, fetch | `pending` |
| 33 | `huggingface-upload` | filesystem, terminal, huggingface | `ready` |
| 34 | `imagenet` | filesystem, pdf-tools | `ready` |
| 35 | `inter-final-performance-analysis` | filesystem, playwright_with_chunk, google_sheet, terminal, fetch | `pending` |
| 36 | `interview-report` | filesystem, word | `ready` |
| 37 | `inventory-sync` | woocommerce, filesystem | `ready` |
| 38 | `landing-task-reminder` | emails, snowflake, pdf-tools, filesystem | `ready` |
| 39 | `language-school` | filesystem, playwright_with_chunk, excel, fetch, terminal | `pending` |
| 40 | `live-transactions` | google-cloud, filesystem | `ready` |
| 41 | `machine-operating` | google-cloud, filesystem, excel | `ready` |
| 42 | `meeting-assign` | fetch, emails, playwright_with_chunk, filesystem | `pending` |
| 43 | `merge-hf-datasets` | huggingface, terminal, filesystem | `ready` |
| 44 | `music-analysis` | excel, google_sheet, terminal | `ready` |
| 45 | `nhl-b2b-analysis` | google_sheet, filesystem, terminal | `ready` |
| 46 | `notion-hr` | filesystem, emails, notion, pdf-tools | `ready` |
| 47 | `notion-movies` | playwright_with_chunk, notion, fetch | `pending` |
| 48 | `notion-personal-website` | filesystem, word, notion | `ready` |
| 49 | `paper-checker` | filesystem, terminal | `ready` |
| 50 | `payable-invoice-checker` | emails, pdf-tools, filesystem, snowflake | `ready` |
| 51 | `personal-website-construct` | memory, github | `ready` |
| 52 | `ppt-analysis` | pptx, filesystem, pdf-tools | `ready` |
| 53 | `price-comparison` | filesystem, terminal, pdf-tools, google-cloud | `ready` |
| 54 | `privacy-desensitization` | filesystem, terminal | `ready` |
| 55 | `reimbursement-form-filler` | filesystem, excel, pdf-tools, terminal | `ready` |
| 56 | `sales-accounting` | memory, excel, filesystem | `ready` |
| 57 | `set-conf-cr-ddl` | emails, google_calendar | `ready` |
| 58 | `shopping-helper` | filesystem, playwright_with_chunk | `pending` |
| 59 | `sla-timeout-monitor` | emails, snowflake, filesystem, pdf-tools, terminal | `ready` |
| 60 | `student-interview` | emails, google_calendar | `ready` |
| 61 | `sync-todo-to-readme` | git, github | `ready` |
| 62 | `task-tracker` | github, notion | `ready` |
| 63 | `travel-expense-reimbursement` | emails, snowflake, pdf-tools, filesystem | `ready` |
| 64 | `university-course-selection` | filesystem, pdf-tools, terminal, excel | `ready` |
| 65 | `update-material-inventory` | google_sheet, woocommerce | `ready` |
| 66 | `verl-dataset` | huggingface, filesystem, fetch | `pending` |
| 67 | `vlm-history-completer` | playwright_with_chunk, google_sheet, arxiv_local, huggingface, fetch | `pending` |
| 68 | `wandb-best-score` | wandb, filesystem, terminal | `ready` |
| 69 | `wandb-shortest-length` | wandb, filesystem, terminal, excel | `ready` |
| 70 | `woocommerce-customer-survey` | woocommerce, emails, google_forms, filesystem | `ready` |
| 71 | `woocommerce-new-product` | woocommerce, filesystem, emails | `ready` |
| 72 | `woocommerce-new-welcome` | woocommerce, filesystem, terminal, google-cloud, emails | `ready` |
| 73 | `woocommerce-product-recall` | woocommerce, emails, google_forms, filesystem | `ready` |
| 74 | `woocommerce-stock-alert` | woocommerce, google_sheet, emails, filesystem | `ready` |
| 75 | `woocommerce-update-cover` | woocommerce | `ready` |

---

## Unsupported Tasks

These tasks require MCP servers that are excluded, thus these tasks are not suported.

| # | Task Name | MCP Servers |
|---|-----------|-------------|
| 1 | `add-bibtex` | scholarly, playwright_with_chunk, filesystem, terminal, fetch |
| 2 | `cooking-guidance` | filesystem, howtocook |
| 3 | `dietary-health` | filesystem, howtocook, excel, terminal |
| 4 | `find-alita-paper` | arxiv_local, filesystem, scholarly |
| 5 | `identify-all-songs` | filesystem, youtube-transcript, playwright_with_chunk, fetch |
| 6 | `investment-decision-analysis` | yahoo-finance, google_sheet, excel, filesystem |
| 7 | `invoice-org` | pdf-tools, filesystem, yahoo-finance, excel |
| 8 | `ipad-edu-price` | yahoo-finance, playwright_with_chunk, fetch |
| 9 | `k8s-deployment-cleanup` | k8s, emails, pdf-tools, filesystem |
| 10 | `k8s-mysql` | k8s, filesystem |
| 11 | `k8s-pr-preview-testing` | terminal, filesystem, playwright_with_chunk, k8s |
| 12 | `k8s-redis-helm-upgrade` | k8s, terminal, filesystem |
| 13 | `k8s-safety-audit` | k8s, google_sheet, filesystem |
| 14 | `latex-prompt-box` | filesystem, arxiv-latex, terminal |
| 15 | `llm-training-dataset` | playwright_with_chunk, google_sheet, scholarly, fetch |
| 16 | `logical-datasets-collection` | filesystem, scholarly, arxiv_local, pdf-tools, fetch |
| 17 | `mrbeast-analysis` | youtube, filesystem, excel, youtube-transcript |
| 18 | `notion-find-job` | google_map, notion, emails, playwright_with_chunk |
| 19 | `nvidia-market` | yahoo-finance, filesystem, terminal, playwright_with_chunk, excel, fetch |
| 20 | `nvidia-stock-analysis` | yahoo-finance, filesystem, terminal, excel |
| 21 | `oil-price` | yahoo-finance, notion, filesystem, terminal |
| 22 | `profile-update-online` | filesystem, playwright_with_chunk, scholarly, arxiv_local, pdf-tools |
| 23 | `quantitative-financial-analysis` | filesystem, yahoo-finance, google_sheet, notion, terminal |
| 24 | `search-ca-school` | filesystem, google_map, playwright_with_chunk, fetch |
| 25 | `stock-build-position` | excel, yahoo-finance, terminal |
| 26 | `subway-planning` | google_map, filesystem, playwright_with_chunk, fetch |
| 27 | `train-ticket-plan` | filesystem, rail_12306, terminal, fetch |
| 28 | `travel-exchange` | terminal, filesystem, yahoo-finance |
| 29 | `trip-adviser` | google_map, fetch, filesystem, playwright_with_chunk |
| 30 | `trip-itinerary-generator` | filesystem, google_map, playwright_with_chunk |
| 31 | `upenn-campus-route` | filesystem, terminal, google_map, fetch |
| 32 | `yahoo-analysis` | yahoo-finance, filesystem, terminal |
| 33 | `youtube-repo` | youtube, youtube-transcript, filesystem, fetch, github |

---
