"""SQLite z szyfrowaniem konfiguracji i sekretnych kluczy instalacji."""
from __future__ import annotations
import json, os, sqlite3, threading
from cryptography.fernet import Fernet

LOCK=threading.RLock()

def db():
    conn=sqlite3.connect(os.getenv('DB_PATH','/data/app.sqlite3'),timeout=20)
    conn.row_factory=sqlite3.Row
    return conn

def fernet():
    key=os.getenv('ENCRYPTION_KEY','')
    if not key:
        raise RuntimeError('Ustaw ENCRYPTION_KEY (python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")')
    return Fernet(key.encode())

def init():
    os.makedirs(os.path.dirname(os.path.abspath(os.getenv('DB_PATH','/data/app.sqlite3'))),exist_ok=True)
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS installs (id TEXT PRIMARY KEY, api_url TEXT NOT NULL, secret BLOB NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS configs (id TEXT NOT NULL, step INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(id,step))')
        c.execute('CREATE TABLE IF NOT EXISTS product_links (id TEXT NOT NULL, sku TEXT NOT NULL, sellasist_id TEXT NOT NULL, PRIMARY KEY(id,sku))')
        c.execute('CREATE TABLE IF NOT EXISTS events (id TEXT NOT NULL, sync_id TEXT NOT NULL, event_name TEXT NOT NULL, sku TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(id,sync_id,event_name,sku))')

def enc(value):
    return fernet().encrypt(json.dumps(value,ensure_ascii=False).encode('utf-8'))

def dec(value):
    return json.loads(fernet().decrypt(value))

def register(installation,api_url,secret):
    with LOCK, db() as c:
        previous=c.execute('SELECT api_url,secret FROM installs WHERE id=?',(installation,)).fetchone()
        if previous and (previous['api_url'] != api_url or dec(previous['secret'])!=secret):
            raise ValueError('Zarejestrowana instalacja ma inne dane uwierzytelnienia')
        c.execute('INSERT OR IGNORE INTO installs VALUES (?,?,?)',(installation,api_url,enc(secret)))

def read_install(installation):
    with db() as c:
        row=c.execute('SELECT * FROM installs WHERE id=?',(installation,)).fetchone()
        return {'api_url':row['api_url'],'secret':dec(row['secret'])} if row else None

def put_step(installation,step,data):
    with LOCK, db() as c:
        c.execute('INSERT INTO configs VALUES (?,?,?) ON CONFLICT(id,step) DO UPDATE SET data=excluded.data',(installation,step,enc(data)))

def get_steps(installation, amount=3):
    with db() as c:
        rows=c.execute('SELECT step,data FROM configs WHERE id=?',(installation,)).fetchall()
    found={r['step']:dec(r['data']) for r in rows}
    return [found.get(i,{}) for i in range(amount)]

def get_link(installation,sku):
    with db() as c:
        row=c.execute('SELECT sellasist_id FROM product_links WHERE id=? AND sku=?',(installation,sku)).fetchone()
        return row[0] if row else None

def put_link(installation,sku,sellasist_id):
    with LOCK, db() as c:
        c.execute('INSERT INTO product_links VALUES (?,?,?) ON CONFLICT(id,sku) DO UPDATE SET sellasist_id=excluded.sellasist_id',(installation,sku,str(sellasist_id)))

def log(installation,sync_id,event,sku,payload,status):
    with LOCK, db() as c:
        c.execute('INSERT INTO events VALUES (?,?,?,?,?,?) ON CONFLICT(id,sync_id,event_name,sku) DO UPDATE SET payload=excluded.payload,status=excluded.status',(installation,sync_id,event,sku,enc(payload).decode(),status))

def logged(installation,sync_id,event,sku):
    with db() as c:
        row=c.execute('SELECT status FROM events WHERE id=? AND sync_id=? AND event_name=? AND sku=?',(installation,sync_id,event,sku)).fetchone()
    return row[0] if row else None

def last_logs(installation,limit=100):
    with db() as c:
        rows=c.execute('SELECT sync_id,event_name,sku,status FROM events WHERE id=? ORDER BY rowid DESC LIMIT ?',(installation,limit)).fetchall()
    return [dict(row) for row in rows]

def uninstall(installation):
    with LOCK, db() as c:
        for table in ('installs','configs','product_links','events'):
            c.execute(f'DELETE FROM {table} WHERE id=?',(installation,))


def preview(installation,sku):
    with db() as c:
        row=c.execute('SELECT sync_id,event_name,status,payload FROM events WHERE id=? AND sku=? ORDER BY rowid DESC LIMIT 1',(installation,sku)).fetchone()
    return {'synchronization_id':row['sync_id'],'event':row['event_name'],'status':row['status'],'payload':dec(row['payload'])} if row else None

def installations():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT id,api_url FROM installs ORDER BY id').fetchall()]
