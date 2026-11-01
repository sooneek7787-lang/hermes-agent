# INFRA_PLAN — Мультиагентная защита от зацикливания

Автономный DevSecOps-аудит координирования субагентов. Дата: 2026-11-01.

## Фаза 1 — Discovery (что уже есть / чего нет)

### Уже в коде (не изобретаем)
| Механизм | Где | Статус |
|---|---|---|
| Лимит итераций на субагента | `delegation.max_iterations` (config.yaml: 250), `DEFAULT_MAX_ITERATIONS` (tools/delegate_tool.py:106) | ✅ |
| Лимит глубины вложенности | `delegation.max_spawn_depth: 2` | ✅ |
| Лимит параллельности | `delegation.max_concurrent_children: 2` | ✅ |
| Таймаут ребёнка | `delegation.child_timeout_seconds: 600` | ✅ |
| Структурированный вывод (JSON-схема) | `delegation.output_schema` (tools/delegation_output_schema.py) + один bounded retry | ✅ |
| Механизм per-request параметров | `request_overrides` → wire merge (agent/transports/chat_completions.py:645,681) | ✅ |
| Env-override паттерн | `_env_int(name, default, minimum)` (hermes_cli/kanban_db.py:80) | ✅ |
| Структурный handoff kanban | `kanban_complete` + `task_events` + `consecutive_failures` | ✅ |

### Гэпы (что добавляем)
1. **Лимит раундов ревью (kanban)** — `request_changes` (hermes_cli/kanban_db.py:3412) не ограничивает число циклов reviewer↔implementer → бесконечный loop правок. **NEW**.
2. **Температура субагентов** — `AIAgent` не принимает temperature; дети наследуют пустые `request_overrides` родителя → температура не зафиксирована, галлюцинации. **NEW**.

## Фаза 2 — Roadmap (контрольные точки)

### a) Окружение и зависимости
- venv: 72 пакета, Python 3.14.7, pytest 9.1.1. **Новых зависимостей нет** (Ponytail: stdlib + существующие механизмы).
- Проверяем: `request_overrides` доходит до wire (подтверждено grep).

### b) Защитные механизмы
- **B1**: `request_changes` — счётчик `changes_requested`-событий; при `>= HERMES_KANBAN_MAX_REVIEW_ROUNDS` (default 3) → reject с инструкцией `complete_task`/`block_task`.
- **B2**: `_build_child_agent` — инжект `delegation.temperature` в `request_overrides` ребёнка (caller key wins).

### c) Инфраструктура взаимодействия
- config.yaml: `delegation.temperature: 0.2`.
- Env: `HERMES_KANBAN_MAX_REVIEW_ROUNDS` (override, default 3).

### d) Тестирование и самодиагностика
- **T1**: `test_request_changes_round_limit_forces_decision` (kanban_db).
- **T2**: `test_apply_delegation_temperature_pins_config_value` (delegate_tool).
- Health-check: прогон обоих тестов + ручной cycle-тест kanban.

## Фаза 3 — Execution
1. `hermes_cli/kanban_db.py`: round-limit в `request_changes`.
2. `tools/delegate_tool.py`: helper `_apply_delegation_temperature` + вызов в `_build_child_agent`.
3. `config.yaml`: `delegation.temperature: 0.2`.
4. Тесты T1, T2.
5. Прогон тестов, health-check.

## Фаза 4 — Maintenance
- Health-check скрипт: `pytest tests/hermes_cli/test_kanban_review_lifecycle.py tests/agent/test_subagent_lifecycle.py -k "round_limit or temperature"`.
- Отчёт: этот файл + summary в чат.
