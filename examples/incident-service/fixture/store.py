import sqlite3

class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS incident(id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=5)
    def create(self, title):
        with self.connect() as db:
            row = db.execute('INSERT INTO incident(title,status) VALUES (?,?)',(title,'open'))
            return {'id':row.lastrowid,'title':title,'status':'open'}
    def list(self, limit=20, offset=0):
        with self.connect() as db:
            rows = db.execute('SELECT id,title,status FROM incident ORDER BY id DESC LIMIT ? OFFSET ?',(limit,offset)).fetchall()
        return [dict(zip(('id','title','status'),r)) for r in rows]
    def update(self, identifier, status):
        with self.connect() as db:
            row = db.execute('UPDATE incident SET status=? WHERE id=?',(status,identifier))
            return row.rowcount > 0
    def health(self):
        with self.connect() as db:
            db.execute('SELECT id FROM incident LIMIT 1').fetchall()
