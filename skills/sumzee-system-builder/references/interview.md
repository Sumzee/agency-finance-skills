# Interview

Goal: understand the **entities** of the business — what is sold, to whom, who does
the work, where money comes in and goes out — not to collect numbers. 10–15 minutes.

Rules:
- Ask in the owner's language. Russian and English wording is given; adapt the tone.
- Use a question widget with options when one is available (AskUserQuestion in Claude
  apps); otherwise numbered options in one message. Max 4 questions per round, max
  3 rounds. Always allow "other".
- Skip what you already know: from Profit Agent's results, from attached files, from
  earlier messages. Say what you took from where in one line ("Модель — проекты, это я
  взял из разбора прибыли").
- If they attach spreadsheets, look at them first (header rows, columns, distinct values
  of short text columns) — they answer many questions without asking.
- After each round, play back in 2–3 lines what you understood. Wrong understanding is
  cheaper to fix now than after the schema.

## Round 1 — model and scale

1. **Как вы зарабатываете?** / How do you make money?
   Проекты по договору · Ежемесячные ретейнеры · Абонементы / пакеты занятий / подписки ·
   Запуски (курсы, мероприятия) · Смесь (какая?)
   → picks the template (`projects`, `retainers`, `subscriptions`, `launches`). A mix:
   take the dominant model as the template and add the other's tables by hand.
2. **Масштаб за год** / Scale per year: сколько клиентов (или участников), сделок/абонементов,
   оплат, трат? Ranges are fine: до 50 · 50–200 · 200–1 000 · больше.
   → `estimated_records`, free-plan check.
3. **Сколько юрлиц, счетов и валют?** / Legal entities, accounts, currencies?
   Одно юрлицо, одна валюта · Несколько счетов · Несколько валют (каких?) · Несколько юрлиц
   → `--currencies` (multicurrency module only if more than one), Accounts rows.
4. **Где всё живёт сейчас?** / Where does it live now?
   Excel / Google Sheets · Airtable · Notion · CRM (какая?) · Бухгалтерская программа · В голове и чатах
   → sources for migration; an existing Airtable base is read as a source, never modified.

## Round 2 — how money and work flow

5. **Как приходят деньги?** / How does money come in?
   Счёт на юрлицо · Карта / онлайн-оплата · Наличные · На личные карты · Через платформу (какую?)
   → Payments.Method / Platform choices, Accounts for personal cards and cash.
6. **Кто делает работу и как платите?** / Who does the work, how are they paid?
   Только я · Штат на окладе · Подрядчики почасово · Подрядчики за проект · Смесь
   → Team; hours and hour cost only if they want project/client margin.
7. **Считаете ли время?** / Do you track time? Да, в таблице/сервисе · Нет, но хотим · Нет и не нужно
   → Hours table yes/no. "No and not needed" + project model: drop Hours, margin =
   contract − direct costs, and say what is lost.
8. **Траты: кто платит, кто согласует, есть ли бюджеты?** / Spending: who pays, approves, budgets?
   → personal_cards module, budgets module, Expenses.Status choices.

## Round 3 — what they want to see (always ask)

9. **Что хотите видеть раз в месяц?** / What do you want to see every month? (multi-select)
   Прибыль по месяцам · Маржу по проектам/клиентам · Кто должен денег · Остатки на счетах ·
   Загрузку команды · План/факт по бюджетам · Активные абонементы / подписки · Окупаемость запусков
   → `questions` on the schema page; drop tables nobody needs for these.
10. **Кто будет вносить данные и сколько времени готов тратить?** / Who enters data, how much time?
   Я сам, 15 минут в неделю · Ассистент/админ · Каждый своё (часы, траты) · Хотим максимум автоматически
   → `entered_by`, forms, how much to simplify. A system nobody fills is worse than a
   spreadsheet: if the answer is "15 minutes a week, me alone", cut to the core +
   the one thing they care about most.
11. **Как вы называете вещи?** / What do you call things? (open, optional)
   Their words become table labels and select options: «тренинги», «потоки», «ученики».

## When answers are thin

If after round 2 you still can't tell the model or the answers are one-word: say so
honestly, propose the closest template as is ("возьмём проектный шаблон, как у BEsmart,
и поправим по ходу"), and move to the schema. Don't invent custom tables from guesses.

## When a system isn't needed

1–2 clients, no team, one currency, a handful of payments a month: tell them a simple
spreadsheet is enough and offer Profit Agent instead. This honesty is part of the
Sumzee approach.

## From Profit Agent

If the conversation or attached files contain Profit Agent output (`results.json`,
`mapping.json`, `narrative.json` or the dashboard), take:
- business model → template;
- `cost_breakdown` categories → Categories rows (seed them during migration);
- `revenue_by_client` → Clients rows;
- `locked` / `opportunities` and their `missing` items → what the system must collect
  (e.g. "team hours per project" → Hours table is a must);
- excluded items (owner draws, transfers) → Expenses.Kind / Payments.Kind choices;
- the original files → the migration source.
