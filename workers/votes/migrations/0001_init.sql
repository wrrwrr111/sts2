CREATE TABLE IF NOT EXISTS vote_counters (
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  like_count INTEGER NOT NULL DEFAULT 0,
  dislike_count INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS vote_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('like', 'dislike')),
  actor_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vote_events_actor_target_action_time
  ON vote_events (actor_hash, entity_type, entity_id, action, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vote_events_target_time
  ON vote_events (entity_type, entity_id, created_at DESC);
