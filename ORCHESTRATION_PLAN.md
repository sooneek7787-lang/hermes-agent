# Оркестрационная система CTO — план A→Я

Дата: 2026-11-01. Статус: план, к исполнению.
Источники: GitHub (gh CLI), Hermes Hub, локальные скиллы, ECC docs.

---

## 0. Что уже есть (инвентарь — не дублировать)

| Слой | Механизм | Статус |
|------|----------|--------|
| CTO (я) | SOUL.md: планировать, решать, принимать | есть |
| В-сессии fan-out | `delegate_task` (max 2, isolated context) | есть |
| Долгие миссии | kanban swarm (7 ролей, durable, review-lane) | есть |
| Role→skills | `_ECC_ROLE_SKILLS` (f0ed56ecfa) — воркер получает ECC-агента роли | есть |
| Fan-out + adversarial | `dynamic-workflow` (official, локальный) | есть |
| Workflow-паттерны | superpowers v7.0.1 (dispatching-parallel-agents, subagent-driven-development, verification-before-completion, requesting/receiving-code-review) | есть |
| Ограничение циклов | c288768ad8: max 3 review rounds, delegation.temperature 0.2 | есть |
| Знание | fact_store + RAG + lessons (shared, /mem/lessons) | есть |
| Наблюдение | kanban_heartbeat, message count, agent.log | есть |

**Вывод:** механизмы есть. Не хватает **контрактов** — как CTO формулирует задание, как воркер отдаёт результат, как CTO принимает. Это и есть «harness».

---

## 1. Паттерны из исследований (GitHub + Hub)

### 1.1 opencode-workspace (586★, kdcokenny)
- Архитектура: **Orchestrators (plan/build) → Specialists (explore/researcher/coder/scribe/reviewer)**.
- Bundle: 4 plugins + 4 agents + 4 skills + permission boundaries.
- Урок: оркестратор не исполняет — он планирует и делегирует; специалисты изолированы по правам (researcher read-only, scribe no-bash).

### 1.2 OAK (144★, jcarlosrodicio)
- **Bounded engineering workflows**: durable state, explicit handoffs, independent review, validation evidence, optional human approval gates.
- Ключевое правило: *«Small, clear, low-risk changes go directly to implementation. Larger or ambiguous work follows a structured flow with research, planning, review, and evidence.»*
- Урок: не гнать всё через тяжёлый процесс — размер задачи определяет глубину оркестрации.

### 1.3 ECC LANE-RULES (coordination contract)
- **One task, one branch, one PR or one receipt, then stop.**
- Worker: real work only (edit, test, commit, push, PR/receipt).
- **Receipt < 300 words**: what changed, PR link, test command and result, what is blocked and on whom.
- **Never merge to main / deploy / publish unless the brief says so explicitly.**
- **If blocked — stop and say exactly what is needed. Do not wait, poll, or sleep.**
- **Time box: finish in one pass. Do not spawn subagents.**
- Урок: воркер ограничен по времени, результату и правам; CTO получает receipt, а не нарратив.

### 1.4 ECC verification-loop (11.8k installs)
- 6 фаз: build → type check → lint → tests+coverage → security grep → diff review → **PASS/FAIL report**.
- Урок: приёмка = детерминированные фазы с exit-кодами, не «похоже работает».

### 1.5 superpowers (наш референс, локальный)
- dispatching-parallel-agents: **one agent per independent problem domain**; shared state → sequential.
- verification-before-completion: «'done' means every named acceptance criterion is verified».
- Урок: независимость задач → параллель; общее состояние → последовательный.

### 1.6 Hermes Hub (skills.sh)
- `dynamic-workflow` (official) — уже локален.
- `verification-loop` (ECC, 11.8k) — кандидат на импорт.
- `wayfinder` (755k installs) — навигация по кодовой базе (исследовать при необходимости).
- `agent-team-builder` (246) — генерация команд (нам не нужен — роли уже есть).
- Урок: Hub — источник отдельных скиллов, не целых систем.

---

## 2. Дизайн: 3 слоя оркестрации

```
┌─────────────────────────────────────────────────────────────┐
│                        CTO (я)                              │
│  - беседует с оператором                                     │
│  - решает: какой слой, какой агент, какой контракт            │
│  - принимает: receipt + verification                         │
└────────────────────────────┬────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐  ┌─────────▼─────────┐  ┌──────▼───────┐
│  СЛОЙ 1:      │  │  СЛОЙ 2:         │  │  СЛОЙ 3:      │
│  В-СЕССИИ     │  │  ДОЛГИЕ МИССИИ   │  │  FAN-OUT      │
│  delegate_task│  │  kanban swarm    │  │  dynamic-     │
│  (max 2)      │  │  (7 roles)       │  │  workflow     │
│              │  │                  │  │  (waves)      │
│ < 10 единиц  │  │  1–2 ч, durable  │  │  100+ файлов, │
│ рассуждение  │  │  review-lane     │  │  multi-angle  │
│ контекст     │  │  ECC role→skills │  │  adversarial  │
└───────────────┘  └──────────────────┘  └───────────────┘
```

**Выбор слоя (правило CTO):**
- `< 10 единиц работы`, рассуждение, контекст → **Слой 1** (delegate_task).
- Долгая миссия (1–2 ч), должна пережить рестарт, нужен review → **Слой 2** (kanban).
- 100+ файлов, multi-angle, adversarial verification → **Слой 3** (dynamic-workflow).
- Неясно → **Слой 2** (durable, можно review).

---

## 3. Контракты (главный gap)

### 3.1 Brief (CTO → воркер)
**Формат** (в kanban task body / delegate_task context):
```
## Задача
<что должно стать правдой после задачи — exit-критерий>

## Exit-критерии (машинно-проверяемые)
- <команда, файл, число — что CTO будет проверять>

## Контекст (воркер ничего не знает о сессии CTO)
- <файлы, ограничения, что уже сделано>

## Границы
- <что НЕ трогать, что НЕ коммитить, что НЕ деплоить>

## Receipt (что воркер вернёт)
- what changed, test command + result, what is blocked and on whom
- < 300 words
```
**Правило:** воркер пишет fact_store с task-тегами по ходу (крах на последнем ходе теряет report.md, но сохраняет факты).

### 3.2 Receipt (воркер → CTO)
**Формат** (kanban_complete / delegate_task summary):
```
## Что изменилось
<файлы, commits>

## Проверка
<test command + result (exit code)>

## Что заблокировано
<что нужно от CTO/оператора, или «ничего»>

## Факты
<task-теги в fact_store>
```
**Правило:** receipt < 300 words. Не нарратив, не «похоже работает».

### 3.3 Verification (CTO → receipt)
**Формат** (ECC verification-loop, адаптирован под наш стек):
```
Phase 1: Build — .venv/bin/python3 -m compileall <files> (exit 0)
Phase 2: Type — pyright <files> (0 errors, или known pre-existing)
Phase 3: Lint — ruff check <files> (exit 0)
Phase 4: Tests — pytest <relevant tests> (no new failures vs baseline)
Phase 5: Security — grep для secrets, new deps
Phase 6: Diff — git diff <commit> (только ожидаемые файлы)
→ PASS/FAIL report
```
**Правило:** CTO проверяет **сам** (не верит receipt). Ответа инструмента достаточно, если он подтверждает exit-критерий.

### 3.4 Escalation (воркер → CTO)
**Правило:** воркер заблокирован → **stop and say exactly what is needed. Do not wait, poll, or sleep.**
- CTO решает: дать контекст, сменить агента, эскалировать оператору.
- Оператору — только при необратимости или стоимости.

---

## 4. Реализация (шаги, файлы, commits)

### Шаг 1: Скилл `cto-brief-receipt` (контракт)
**Файл:** `~/.hermes/skills/cto-brief-receipt/SKILL.md`
**Содержание:** §3.1–3.4 выше (brief, receipt, verification, escalation).
**Почему скилл, а не SOUL:** контракты — процедуры, не правила. SOUL — политика.
**Коммит:** — (скилл не в git, nightly backup).

### Шаг 2: Импорт `verification-loop` из ECC (Hub)
**Команда:** `hermes skills install skills-sh/affaan-m/ecc/verification-loop`
**Почему:** 6-фазный PASS/FAIL gate — готовый, 11.8k installs, MIT.
**Адаптация:** наши команды (pytest, pyright, ruff) уже в §3.3 — скилл дополняет, не дублирует.
**Коммит:** — (скилл не в git).

### Шаг 3: Обновить `hermes-agent-teams` скилл (процедуры)
**Файл:** `~/.hermes/skills/hermes-agent-teams/SKILL.md`
**Добавить:** §3.1–3.4 (контракты) + выбор слоя (§2).
**Почему:** hermes-agent-teams — уже скилл процедур оркестрации. Контракты — туда.
**Коммит:** — (скилл не в git).

### Шаг 4: Обновить SOUL.md (политика)
**Файл:** `~/.hermes/SOUL.md`
**Добавить:** одно правило: *«CTO: выбор слоя по §2, контракты по cto-brief-receipt, verification по verification-loop.»*
**Почему:** SOUL — указатель на контракты, не сами контракты.
**Коммит:** — (SOUL не в git, nightly backup).

### Шаг 5: Проверить (live)
**Тест:** создать kanban task (assignee=coder), проверить что воркер получает ECC-скилл + brief-контракт.
**Проверка:** `hermes kanban create "test" --assignee coder` → воркер стартует → receipt → CTO verification.
**Exit-критерий:** воркер вернул receipt < 300 words, CTO проверил PASS/FAIL.

---

## 5. Что НЕ делаем (Ponytail — не дублировать)

- **Не добавляем новые механизмы** (plugins, MCP, npm deps). Контракты — скиллы + SOUL.
- **Не дублируем dynamic-workflow** (уже official, локальный).
- **Не дублируем superpowers** (v7.0.1, workflow-паттерны).
- **Не добавляем agent-team-builder** (роли уже есть, kanban.db).
- **Не гоним всё через kanban** (OAK: small/low-risk → direct implementation).

---

## 6. Риск и откат

- **Риск:** контракты — текстовые, не кодовые. Воркер может не следовать.
  - **Митигация:** receipt < 300 words (ограничение), verification — детерминированные фазы (exit-коды).
- **Откат:** удалить скиллы `cto-brief-receipt`, `verification-loop`, откатить SOUL.md и hermes-agent-teams (git stash / nightly backup).
- **Обратимость:** все шаги — текстовые правки (скиллы, SOUL). Нет кода, нет config.yaml, нет новых deps.

---

## 7. Дальше (пока не в scope)

- **ECC Phase 2/3** (full install, Memory Vault) — по решению оператора.
- **wayfinder** (755k installs) — навигация по кодовой базе — при необходимости.
- **Observability** (agent.log → dashboard) — при необходимости.
- **Approval gates** (human-in-the-loop) — при необходимости (OAK: optional).
