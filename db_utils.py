# db_utils.py

import sqlite3

def create_tables_and_indices(conn):
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE);
            """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS fingerprints (
            hash TEXT,
            offset INTEGER,
            song_id INTEGER,
            FOREIGN KEY(song_id) REFERENCES songs(id));
        """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_hash ON fingerprints(hash);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_song_id ON fingerprints(song_id);")
    conn.commit()

def song_in_db(conn, filename):
    c = conn.cursor()
    c.execute("SELECT id FROM songs WHERE filename=?", (filename,))
    row = c.fetchone()
    return row[0] if row else None

def add_song_to_db(conn, filename):
    c = conn.cursor()
    c.execute("INSERT INTO songs (filename) VALUES (?)", (filename,))
    conn.commit()
    return c.lastrowid

def add_fingerprints_bulk(conn, song_id, fingerprints, batch_size=2000):
    c = conn.cursor()
    # SAFETY: Always insert plain int for offset, str for hash
    records = []
    for h, t in fingerprints:
        # If hash is bytes, decode
        if isinstance(h, bytes):
            h = h.decode("utf-8")
        h = str(h)
        # Always ensure int (not np.int64 etc)
        t = int(t)
        records.append((h, t, song_id))
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        c.executemany("INSERT INTO fingerprints (hash, offset, song_id) VALUES (?, ?, ?)", batch)
    conn.commit()
