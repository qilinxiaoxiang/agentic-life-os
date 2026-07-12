PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_focus (
  focus_date TEXT PRIMARY KEY,
  headline TEXT NOT NULL,
  brief TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'manual',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
  due_date TEXT,
  estimated_minutes INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
  source TEXT NOT NULL DEFAULT 'manual',
  sort_order INTEGER NOT NULL DEFAULT 0,
  completed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status_sort ON tasks(status, sort_order, created_at);

CREATE TABLE IF NOT EXISTS money_accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL CHECK (account_type IN ('asset', 'liability')),
  currency TEXT NOT NULL,
  balance_minor INTEGER NOT NULL DEFAULT 0 CHECK (balance_minor >= 0),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS money_budget_items (
  id TEXT PRIMARY KEY,
  month TEXT NOT NULL,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('expense', 'income')),
  amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
  currency TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_money_budget_month ON money_budget_items(month, currency, sort_order);

CREATE TABLE IF NOT EXISTS money_transactions (
  id TEXT PRIMARY KEY,
  external_id TEXT UNIQUE,
  occurred_on TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('expense', 'income', 'refund', 'transfer')),
  account_id TEXT NOT NULL REFERENCES money_accounts(id),
  to_account_id TEXT REFERENCES money_accounts(id),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  currency TEXT NOT NULL,
  category TEXT NOT NULL,
  budget_item_id TEXT REFERENCES money_budget_items(id),
  note TEXT NOT NULL,
  proposal_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_money_transactions_date ON money_transactions(occurred_on, currency);

CREATE TABLE IF NOT EXISTS time_budget_items (
  id TEXT PRIMARY KEY,
  week_start TEXT NOT NULL,
  label TEXT NOT NULL,
  category TEXT NOT NULL,
  weekly_minutes INTEGER NOT NULL CHECK (weekly_minutes >= 0),
  protection TEXT NOT NULL DEFAULT 'flexible'
    CHECK (protection IN ('committed', 'protected', 'flexible')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_time_budget_week ON time_budget_items(week_start, sort_order);

CREATE TABLE IF NOT EXISTS time_entries (
  id TEXT PRIMARY KEY,
  external_id TEXT UNIQUE,
  entry_date TEXT NOT NULL,
  minutes INTEGER NOT NULL CHECK (minutes > 0),
  budget_item_id TEXT REFERENCES time_budget_items(id),
  activity TEXT NOT NULL,
  counts_toward_clock INTEGER NOT NULL DEFAULT 1 CHECK (counts_toward_clock IN (0, 1)),
  overlap_group TEXT,
  unbudgeted INTEGER NOT NULL DEFAULT 0 CHECK (unbudgeted IN (0, 1)),
  note TEXT NOT NULL DEFAULT '',
  proposal_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_entries(entry_date);

CREATE TABLE IF NOT EXISTS ledger_proposals (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('money', 'time')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'committed')),
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  preview_json TEXT NOT NULL,
  result_json TEXT,
  created_at TEXT NOT NULL,
  committed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_proposals_kind_hash ON ledger_proposals(kind, payload_hash);
