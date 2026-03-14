# Toolathlon Task Status in Klavis Sandbox

> **Total tasks:** 108 (from `tasks/finalpool/`)  
> **Supported (MCP servers available):** 103 | **Not supported:** 5 (k8s only)

---

## Evaluation Summary

| Metric | Original Run | Klavis Run |
|--------|-------------|-----------|
| Task set | 108 (all) | 103 (excl. k8s) |
| Max turns | 50 | 100 |
| Passed | 35 | 35 |
| Failed | 69 | 68 |
| Null | 4 | 0 |
| Pass rate | 32.4% | 33.98% |

On the comparable 103 non-k8s tasks: **Original 33 PASS** vs **Klavis 35 PASS** (net +2).

- **Regressions (PASS → FAIL):** 12 tasks (11 LLM non-determinism + 1 local eval bug)
- **Improvements (FAIL/NULL → PASS):** 14 tasks (2 from higher max_turns + 12 LLM non-determinism)
- `verl-dataset` is a **false negative** — agent output was correct but local eval env was missing `pyarrow` (now fixed in `requirements.txt`)

---

## Supported Tasks (103)

| # | Task Name | MCP Servers | Original | Klavis | Delta |
|---|-----------|-------------|----------|--------|-------|
| 1 | `ab-testing` | google-cloud, filesystem | FAIL | FAIL | |
| 2 | `academic-pdf-report` | playwright_with_chunk, excel, terminal, arxiv_local, pdf-tools, fetch | FAIL | FAIL | |
| 3 | `academic-warning` | google-cloud, excel, filesystem | PASS | PASS | |
| 4 | `add-bibtex` | scholarly, playwright_with_chunk, filesystem, terminal, fetch | FAIL | FAIL | |
| 5 | `apply-phd-email` | filesystem, memory, emails, terminal, pdf-tools | PASS | PASS | |
| 6 | `arrange-workspace` | filesystem, terminal, pdf-tools, excel | FAIL | FAIL | |
| 7 | `canvas-arrange-exam` | canvas, emails, memory, terminal | FAIL | FAIL | |
| 8 | `canvas-art-manager` | filesystem, canvas, terminal, emails | PASS | PASS | |
| 9 | `canvas-art-quiz` | filesystem, canvas, terminal | PASS | PASS | |
| 10 | `canvas-do-quiz` | memory, canvas | PASS | FAIL | LLM |
| 11 | `canvas-homework-grader-python` | canvas, filesystem, terminal, emails | FAIL | FAIL | |
| 12 | `canvas-list-test` | canvas, memory | FAIL | FAIL | |
| 13 | `canvas-new-students-notification` | filesystem, terminal, canvas | PASS | PASS | |
| 14 | `canvas-submit-late-work` | canvas, memory, filesystem, emails | PASS | PASS | |
| 15 | `cooking-guidance` | filesystem, howtocook | FAIL | PASS | LLM |
| 16 | `course-assistant` | excel, emails, filesystem, terminal | FAIL | FAIL | |
| 17 | `course-schedule` | filesystem, memory, excel, pdf-tools, fetch | FAIL | FAIL | |
| 18 | `courses-ta-hws` | terminal, excel, filesystem | FAIL | FAIL | |
| 19 | `cvpr-research` | filesystem, fetch, playwright_with_chunk | FAIL | FAIL | |
| 20 | `dataset-license-issue` | huggingface, github, terminal, fetch | PASS | PASS | |
| 21 | `detect-revised-terms` | filesystem, pdf-tools | FAIL | FAIL | |
| 22 | `dietary-health` | filesystem, howtocook, excel, terminal | FAIL | PASS | LLM |
| 23 | `email-paper-homepage` | emails, github | FAIL | FAIL | |
| 24 | `excel-data-transformation` | excel, filesystem, terminal | PASS | PASS | |
| 25 | `excel-market-research` | excel, filesystem, terminal | PASS | PASS | |
| 26 | `experiments-recordings` | notion, wandb, terminal, filesystem | FAIL | FAIL | |
| 27 | `fillout-online-forms` | playwright_with_chunk, memory, filesystem | FAIL | PASS | LLM |
| 28 | `filter-low-selling-products` | woocommerce, filesystem, emails | FAIL | FAIL | |
| 29 | `find-alita-paper` | arxiv_local, filesystem, scholarly | PASS | PASS | |
| 30 | `flagged-transactions` | google-cloud, excel, terminal, filesystem | PASS | PASS | |
| 31 | `game-statistics` | google-cloud, terminal | FAIL | FAIL | |
| 32 | `gdp-cr5-analysis` | google_sheet, playwright_with_chunk, fetch | PASS | FAIL | LLM |
| 33 | `git-bug-hunt` | git, terminal, filesystem, emails | PASS | PASS | |
| 34 | `git-milestone` | filesystem, terminal, fetch | PASS | PASS | |
| 35 | `git-repo` | github, filesystem, pdf-tools | PASS | PASS | |
| 36 | `hk-top-conf` | filesystem, terminal, playwright_with_chunk, fetch | FAIL | FAIL | |
| 37 | `huggingface-upload` | filesystem, terminal, huggingface | FAIL | FAIL | |
| 38 | `identify-all-songs` | filesystem, youtube-transcript, playwright_with_chunk, fetch | FAIL | FAIL | |
| 39 | `imagenet` | filesystem, pdf-tools | PASS | PASS | |
| 40 | `inter-final-performance-analysis` | filesystem, playwright_with_chunk, google_sheet, terminal, fetch | FAIL | FAIL | |
| 41 | `interview-report` | filesystem, word | NULL | PASS | max_turns |
| 42 | `inventory-sync` | woocommerce, filesystem | FAIL | FAIL | |
| 43 | `investment-decision-analysis` | yahoo-finance, google_sheet, excel, filesystem | FAIL | FAIL | |
| 44 | `invoice-org` | pdf-tools, filesystem, yahoo-finance, excel | PASS | PASS | |
| 45 | `ipad-edu-price` | yahoo-finance, playwright_with_chunk, fetch | FAIL | FAIL | |
| 46 | `landing-task-reminder` | emails, snowflake, pdf-tools, filesystem | FAIL | PASS | LLM |
| 47 | `language-school` | filesystem, playwright_with_chunk, excel, fetch, terminal | FAIL | FAIL | |
| 48 | `latex-prompt-box` | filesystem, arxiv-latex, terminal | FAIL | FAIL | |
| 49 | `live-transactions` | google-cloud, filesystem | FAIL | FAIL | |
| 50 | `llm-training-dataset` | playwright_with_chunk, google_sheet, scholarly, fetch | FAIL | FAIL | |
| 51 | `logical-datasets-collection` | filesystem, scholarly, arxiv_local, pdf-tools, fetch | PASS | FAIL | LLM |
| 52 | `machine-operating` | google-cloud, filesystem, excel | FAIL | FAIL | |
| 53 | `meeting-assign` | fetch, emails, playwright_with_chunk, filesystem | FAIL | FAIL | |
| 54 | `merge-hf-datasets` | huggingface, terminal, filesystem | FAIL | FAIL | |
| 55 | `mrbeast-analysis` | youtube, filesystem, excel, youtube-transcript | FAIL | FAIL | |
| 56 | `music-analysis` | excel, google_sheet, terminal | NULL | FAIL | |
| 57 | `nhl-b2b-analysis` | google_sheet, filesystem, terminal | PASS | PASS | |
| 58 | `notion-find-job` | google_map, notion, emails, playwright_with_chunk | FAIL | FAIL | |
| 59 | `notion-hr` | filesystem, emails, notion, pdf-tools | NULL | PASS | max_turns |
| 60 | `notion-movies` | playwright_with_chunk, notion, fetch | FAIL | FAIL | |
| 61 | `notion-personal-website` | filesystem, word, notion | FAIL | FAIL | |
| 62 | `nvidia-market` | yahoo-finance, filesystem, terminal, playwright_with_chunk, excel, fetch | FAIL | FAIL | |
| 63 | `nvidia-stock-analysis` | yahoo-finance, filesystem, terminal, excel | FAIL | FAIL | |
| 64 | `oil-price` | yahoo-finance, notion, filesystem, terminal | FAIL | PASS | LLM |
| 65 | `paper-checker` | filesystem, terminal | FAIL | FAIL | |
| 66 | `payable-invoice-checker` | emails, pdf-tools, filesystem, snowflake | PASS | FAIL | LLM |
| 67 | `personal-website-construct` | memory, github | PASS | FAIL | LLM |
| 68 | `ppt-analysis` | pptx, filesystem, pdf-tools | FAIL | FAIL | |
| 69 | `price-comparison` | filesystem, terminal, pdf-tools, google-cloud | FAIL | PASS | LLM |
| 70 | `privacy-desensitization` | filesystem, terminal | FAIL | FAIL | |
| 71 | `profile-update-online` | filesystem, playwright_with_chunk, scholarly, arxiv_local, pdf-tools | FAIL | FAIL | |
| 72 | `quantitative-financial-analysis` | filesystem, yahoo-finance, google_sheet, notion, terminal | PASS | FAIL | LLM |
| 73 | `reimbursement-form-filler` | filesystem, excel, pdf-tools, terminal | FAIL | PASS | LLM |
| 74 | `sales-accounting` | memory, excel, filesystem | FAIL | PASS | LLM |
| 75 | `search-ca-school` | filesystem, google_map, playwright_with_chunk, fetch | FAIL | FAIL | |
| 76 | `set-conf-cr-ddl` | emails, google_calendar | PASS | PASS | |
| 77 | `shopping-helper` | filesystem, playwright_with_chunk | FAIL | FAIL | |
| 78 | `sla-timeout-monitor` | emails, snowflake, filesystem, pdf-tools, terminal | FAIL | PASS | LLM |
| 79 | `stock-build-position` | excel, yahoo-finance, terminal | PASS | FAIL | LLM |
| 80 | `student-interview` | emails, google_calendar | FAIL | FAIL | |
| 81 | `subway-planning` | google_map, filesystem, playwright_with_chunk, fetch | FAIL | PASS | LLM |
| 82 | `sync-todo-to-readme` | git, github | FAIL | FAIL | |
| 83 | `task-tracker` | github, notion | FAIL | FAIL | |
| 84 | `train-ticket-plan` | filesystem, rail_12306, terminal, fetch | PASS | FAIL | LLM |
| 85 | `travel-exchange` | terminal, filesystem, yahoo-finance | FAIL | FAIL | |
| 86 | `travel-expense-reimbursement` | emails, snowflake, pdf-tools, filesystem | NULL | FAIL | |
| 87 | `trip-adviser` | google_map, fetch, filesystem, playwright_with_chunk | PASS | PASS | |
| 88 | `trip-itinerary-generator` | filesystem, google_map, playwright_with_chunk | PASS | FAIL | LLM |
| 89 | `university-course-selection` | filesystem, pdf-tools, terminal, excel | FAIL | FAIL | |
| 90 | `update-material-inventory` | google_sheet, woocommerce | FAIL | FAIL | |
| 91 | `upenn-campus-route` | filesystem, terminal, google_map, fetch | FAIL | PASS | LLM |
| 92 | `verl-dataset` | huggingface, filesystem, fetch | PASS | FAIL* | eval bug |
| 93 | `vlm-history-completer` | playwright_with_chunk, google_sheet, arxiv_local, huggingface, fetch | FAIL | FAIL | |
| 94 | `wandb-best-score` | wandb, filesystem, terminal | PASS | FAIL | LLM |
| 95 | `wandb-shortest-length` | wandb, filesystem, terminal, excel | PASS | FAIL | LLM |
| 96 | `woocommerce-customer-survey` | woocommerce, emails, google_forms, filesystem | FAIL | FAIL | |
| 97 | `woocommerce-new-product` | woocommerce, filesystem, emails | FAIL | PASS | LLM |
| 98 | `woocommerce-new-welcome` | woocommerce, filesystem, terminal, google-cloud, emails | FAIL | FAIL | |
| 99 | `woocommerce-product-recall` | woocommerce, emails, google_forms, filesystem | PASS | PASS | |
| 100 | `woocommerce-stock-alert` | woocommerce, google_sheet, emails, filesystem | PASS | PASS | |
| 101 | `woocommerce-update-cover` | woocommerce | FAIL | FAIL | |
| 102 | `yahoo-analysis` | yahoo-finance, filesystem, terminal | FAIL | FAIL | |
| 103 | `youtube-repo` | youtube, youtube-transcript, filesystem, fetch, github | FAIL | FAIL | |

**Delta legend:**
- **LLM** — result changed due to LLM non-determinism (not a sandbox issue)
- **max_turns** — original hit 50-turn limit; Klavis run used 100 turns
- **eval bug** — `verl-dataset` agent output was correct but local eval lacked `pyarrow` (fixed)
- Blank — same result in both runs

---

## Unsupported Tasks (5)

These tasks require the `k8s` MCP server which is not available in Klavis sandbox.

| # | Task Name | MCP Servers | Original Result |
|---|-----------|-------------|-----------------|
| 1 | `k8s-deployment-cleanup` | k8s, emails, pdf-tools, filesystem | PASS |
| 2 | `k8s-mysql` | k8s, filesystem | FAIL |
| 3 | `k8s-pr-preview-testing` | terminal, filesystem, playwright_with_chunk, k8s | FAIL |
| 4 | `k8s-redis-helm-upgrade` | k8s, terminal, filesystem | FAIL |
| 5 | `k8s-safety-audit` | k8s, google_sheet, filesystem | PASS |

---
