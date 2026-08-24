from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, os, io, zipfile, html, re
from datetime import date, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'data.db')
app = Flask(__name__, template_folder=os.path.join(BASE,'templates'), static_folder=os.path.join(BASE,'static'))

SCHEMA = '''
CREATE TABLE IF NOT EXISTS purchases (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, material_id TEXT UNIQUE, material_name TEXT NOT NULL,
 material_type TEXT NOT NULL, qty REAL NOT NULL CHECK(qty>=0), unit TEXT NOT NULL,
 rate REAL NOT NULL CHECK(rate>=0), total REAL NOT NULL, seller TEXT DEFAULT '', note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS material_use (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, use_id TEXT UNIQUE NOT NULL,
 material_name TEXT NOT NULL, qty REAL NOT NULL CHECK(qty>0), unit TEXT NOT NULL,
 work_type TEXT NOT NULL, work TEXT DEFAULT '', amount REAL NOT NULL DEFAULT 0,
 unit_rate REAL NOT NULL DEFAULT 0, product_id TEXT DEFAULT NULL, machine_name TEXT DEFAULT '', machine_minutes REAL NOT NULL DEFAULT 0, machine_rate_hour REAL NOT NULL DEFAULT 0, machine_charge REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, product_name TEXT NOT NULL,
 product_id TEXT UNIQUE NOT NULL, material_ids TEXT NOT NULL DEFAULT '', material_cost REAL NOT NULL DEFAULT 0, machine_cost REAL NOT NULL DEFAULT 0,
 labour_percent REAL NOT NULL DEFAULT 0, labour_amount REAL NOT NULL DEFAULT 0,
 profit_percent REAL NOT NULL DEFAULT 0, profit_fixed REAL NOT NULL DEFAULT 0,
 total_product_amount REAL NOT NULL DEFAULT 0, machine_name TEXT DEFAULT '', machine_minutes REAL NOT NULL DEFAULT 0, machine_rate_hour REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sales (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, customer TEXT DEFAULT '', product_id TEXT NOT NULL,
 qty REAL NOT NULL CHECK(qty>0), rate REAL NOT NULL CHECK(rate>=0), amount REAL NOT NULL,
 remark TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'unpaid'
);
CREATE TABLE IF NOT EXISTS daily_work (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, task_id TEXT DEFAULT NULL,
 sales_id TEXT DEFAULT NULL, work_type TEXT NOT NULL, work TEXT NOT NULL,
 tag TEXT DEFAULT '', remark TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT UNIQUE NOT NULL, date TEXT NOT NULL,
 title TEXT NOT NULL, description TEXT DEFAULT '', assigned_to TEXT DEFAULT '',
 priority TEXT NOT NULL DEFAULT 'Medium', status TEXT NOT NULL DEFAULT 'Pending',
 due_date TEXT DEFAULT NULL, tag TEXT DEFAULT '', remark TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS product_materials (
 id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, material_name TEXT NOT NULL,
 material_id INTEGER, qty REAL NOT NULL, unit TEXT NOT NULL, cost REAL NOT NULL
);
'''

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=conn(); c.executescript(SCHEMA)
    cols=[r['name'] for r in c.execute('PRAGMA table_info(purchases)').fetchall()]
    if 'material_id' not in cols: c.execute('ALTER TABLE purchases ADD COLUMN material_id TEXT')
    existing=c.execute("SELECT id FROM purchases WHERE material_id IS NULL OR material_id='' ORDER BY id").fetchall()
    for r in existing: c.execute("UPDATE purchases SET material_id=? WHERE id=?",(f'MAT-{r["id"]:05d}',r['id']))
    # Unique index for older databases after migration.
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_material_id ON purchases(material_id)')
    mu_cols=[r['name'] for r in c.execute('PRAGMA table_info(material_use)').fetchall()]
    if 'unit_rate' not in mu_cols: c.execute('ALTER TABLE material_use ADD COLUMN unit_rate REAL NOT NULL DEFAULT 0')
    if 'product_id' not in mu_cols: c.execute('ALTER TABLE material_use ADD COLUMN product_id TEXT DEFAULT NULL')
    if 'machine_name' not in mu_cols: c.execute("ALTER TABLE material_use ADD COLUMN machine_name TEXT DEFAULT ''")
    if 'machine_minutes' not in mu_cols: c.execute('ALTER TABLE material_use ADD COLUMN machine_minutes REAL NOT NULL DEFAULT 0')
    if 'machine_rate_hour' not in mu_cols: c.execute('ALTER TABLE material_use ADD COLUMN machine_rate_hour REAL NOT NULL DEFAULT 0')
    if 'machine_charge' not in mu_cols: c.execute('ALTER TABLE material_use ADD COLUMN machine_charge REAL NOT NULL DEFAULT 0')
    pm_cols=[r['name'] for r in c.execute('PRAGMA table_info(product_materials)').fetchall()]
    if 'use_id' not in pm_cols: c.execute('ALTER TABLE product_materials ADD COLUMN use_id TEXT DEFAULT NULL')
    prod_cols=[r['name'] for r in c.execute('PRAGMA table_info(products)').fetchall()]
    if 'machine_cost' not in prod_cols: c.execute('ALTER TABLE products ADD COLUMN machine_cost REAL NOT NULL DEFAULT 0')
    if 'machine_name' not in prod_cols: c.execute("ALTER TABLE products ADD COLUMN machine_name TEXT DEFAULT ''")
    if 'machine_minutes' not in prod_cols: c.execute('ALTER TABLE products ADD COLUMN machine_minutes REAL NOT NULL DEFAULT 0')
    if 'machine_rate_hour' not in prod_cols: c.execute('ALTER TABLE products ADD COLUMN machine_rate_hour REAL NOT NULL DEFAULT 0')
    dw_cols=[r['name'] for r in c.execute('PRAGMA table_info(daily_work)').fetchall()]
    if 'task_id' not in dw_cols: c.execute('ALTER TABLE daily_work ADD COLUMN task_id TEXT DEFAULT NULL')
    if 'sales_id' not in dw_cols: c.execute('ALTER TABLE daily_work ADD COLUMN sales_id TEXT DEFAULT NULL')
    if 'tag' not in dw_cols: c.execute('ALTER TABLE daily_work ADD COLUMN tag TEXT DEFAULT ""')
    if 'work_tag' not in dw_cols: c.execute('ALTER TABLE daily_work ADD COLUMN work_tag TEXT DEFAULT ""')
    sales_cols=[r['name'] for r in c.execute('PRAGMA table_info(sales)').fetchall()]
    if 'sale_id' not in sales_cols: c.execute('ALTER TABLE sales ADD COLUMN sale_id TEXT')
    # Backfill stable human-readable Sale IDs for existing records.
    existing_sales=c.execute("SELECT id FROM sales WHERE sale_id IS NULL OR sale_id='' ORDER BY id").fetchall()
    for r in existing_sales: c.execute("UPDATE sales SET sale_id=? WHERE id=?", (f'SAL-{r["id"]:05d}',r["id"]))
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_sale_id ON sales(sale_id)')
    c.commit(); c.close()

def rows(sql,args=()):
    c=conn(); r=[dict(x) for x in c.execute(sql,args).fetchall()]; c.close(); return r

def scalar(sql,args=()):
    c=conn(); x=c.execute(sql,args).fetchone()[0]; c.close(); return x or 0

def f(v):
    try:return float(v or 0)
    except:return 0.0

def s(v): return str(v or '').strip()

def date_filter_clause(start,end,column='date'):
    parts=[]; args=[]
    if start: parts.append(f'{column}>=?'); args.append(start)
    if end: parts.append(f'{column}<=?'); args.append(end)
    return (' WHERE '+' AND '.join(parts)) if parts else '', args

def next_id(prefix, table, field):
    nums=rows(f"SELECT {field} v FROM {table} WHERE {field} LIKE ? ORDER BY id DESC",(prefix+'-%',))
    mx=0
    for r in nums:
        m=re.search(r'(\d+)$',str(r['v'] or ''))
        if m: mx=max(mx,int(m.group(1)))
    return f'{prefix}-{mx+1:05d}'

@app.route('/')
def index(): return render_template('index.html')

@app.route('/dashboard')
def dashboard_page(): return render_template('dashboard.html', today=date.today().isoformat())

@app.get('/api/dashboard')
def dashboard():
    start=s(request.args.get('from')); end=s(request.args.get('to'))
    where,args=date_filter_clause(start,end,'date')
    materials=rows('''SELECT p.material_name,p.unit,
      ROUND(SUM(p.qty),4) purchased, ROUND(COALESCE(u.used,0),4) used,
      ROUND(SUM(p.qty)-COALESCE(u.used,0),4) remaining,
      ROUND((SUM(p.qty)-COALESCE(u.used,0))*SUM(p.total)/NULLIF(SUM(p.qty),0),2) stock_value
      FROM purchases p LEFT JOIN (SELECT material_name,unit,SUM(qty) used FROM material_use GROUP BY material_name,unit) u
      ON p.material_name=u.material_name AND p.unit=u.unit GROUP BY p.material_name,p.unit HAVING remaining>0 ORDER BY p.material_name''')
    sales_total=scalar(f'SELECT SUM(amount) FROM sales{where}',args)
    labour=scalar(f'SELECT SUM(labour_amount) FROM products{where}',args)
    machine_time=scalar(f'SELECT SUM(machine_minutes) FROM products{where}',args)
    machine_charge=scalar(f'SELECT SUM(machine_cost) FROM products{where}',args)
    unpaid=scalar(f"SELECT SUM(amount) FROM sales{where + (' AND ' if where else ' WHERE ')}status='unpaid'",args)
    sales_profit=scalar(f'''SELECT SUM(s.amount-COALESCE((p.material_cost+p.labour_amount),0)*s.qty)
      FROM sales s LEFT JOIN products p ON p.product_id=s.product_id {where.replace('date','s.date')}''',args)
    work=rows(f'''SELECT w.*, t.title AS task_title
        FROM daily_work w LEFT JOIN tasks t ON t.task_id=w.task_id
        {where.replace('date','w.date')} ORDER BY w.id DESC LIMIT 8''',args)
    purchase_total=scalar(f'SELECT SUM(total) FROM purchases{where}',args)
    unpaid_bills=rows(f"SELECT id,sale_id,date,customer,product_id,qty,rate,amount,status,remark FROM sales{where + (' AND ' if where else ' WHERE ')}status='unpaid' ORDER BY date DESC,id DESC",args)
    pending_tasks=rows('''SELECT * FROM tasks WHERE LOWER(status) NOT IN ('completed','done') ORDER BY
        CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, due_date IS NULL, due_date, id DESC LIMIT 12''')
    return jsonify({'materials':materials,'sales_total':sales_total,'sales_profit':sales_profit,'labour':labour,
        'unpaid':unpaid,'unpaid_bills':unpaid_bills,'purchase_total':purchase_total,'recent_work':work,
        'pending_tasks':pending_tasks,'machine_time':machine_time,'machine_charge':machine_charge,'from':start,'to':end})

@app.get('/api/<table>')
def get_table(table):
    allowed={'purchases':'purchases','material_use':'material_use','products':'products','sales':'sales','daily_work':'daily_work','tasks':'tasks'}
    if table not in allowed:return jsonify(error='invalid table'),400
    return jsonify(rows(f'SELECT * FROM {allowed[table]} ORDER BY id DESC'))

@app.get('/api/materials')
def materials():
    return jsonify(rows('''SELECT material_name,unit,ROUND(SUM(qty),4) purchased,
      ROUND(COALESCE((SELECT SUM(m.qty) FROM material_use m WHERE m.material_name=p.material_name AND m.unit=p.unit),0),4) used,
      ROUND(SUM(qty)-COALESCE((SELECT SUM(m.qty) FROM material_use m WHERE m.material_name=p.material_name AND m.unit=p.unit),0),4) remaining,
      ROUND(SUM(total),2) total_cost
      FROM purchases p GROUP BY material_name,unit ORDER BY material_name'''))

@app.get('/api/product-use-options')
def product_use_options():
    return jsonify(rows('''SELECT id,use_id,date,material_name,qty,unit,amount,unit_rate,work_type,work,product_id,machine_name,machine_minutes,machine_rate_hour,machine_charge
      FROM material_use WHERE product_id IS NULL ORDER BY id DESC'''))

@app.get('/api/ids')
def ids(): return jsonify(
    material_id=next_id('MAT','purchases','material_id'),
    product_id=next_id('PROD','products','product_id'),
    use_id=next_id('USE','material_use','use_id'),
    task_id=next_id('TASK','tasks','task_id'),
    sale_id=next_id('SAL','sales','sale_id')
)

@app.get('/api/tasks')
def get_tasks():
    return jsonify(rows('SELECT * FROM tasks ORDER BY id DESC'))

@app.get('/api/task-options')
def task_options():
    return jsonify(rows("SELECT task_id,title,status FROM tasks WHERE LOWER(status) NOT IN ('completed','done') ORDER BY id DESC"))

@app.get('/api/sale-options')
def sale_options():
    return jsonify(rows("SELECT sale_id,customer,product_id,status,amount FROM sales ORDER BY id DESC"))

@app.post('/api/tasks')
def add_task():
    d=request.json or {}
    tid=next_id('TASK','tasks','task_id')
    title=s(d.get('title'))
    if not title: return jsonify(error='Task title is required.'),400
    status=s(d.get('status')) or 'Pending'
    if status.lower()=='done': status='Completed'
    c=conn()
    try:
        c.execute('INSERT INTO tasks(task_id,date,title,description,assigned_to,priority,status,due_date,tag,remark) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (tid,s(d.get('date')) or date.today().isoformat(),title,s(d.get('description')),s(d.get('assigned_to')),
                   s(d.get('priority')) or 'Medium',status,s(d.get('due_date')) or None,s(d.get('tag')),s(d.get('remark'))))
        c.commit()
    except Exception as e:
        c.rollback(); c.close(); return jsonify(error=str(e)),400
    c.close(); return jsonify(ok=True,task_id=tid)

@app.post('/api/purchases')
def add_purchase():
    d=request.json; q=f(d.get('qty')); rate=f(d.get('rate')); total=round(q*rate,2); mid=next_id('MAT','purchases','material_id')
    c=conn(); c.execute('INSERT INTO purchases(date,material_id,material_name,material_type,qty,unit,rate,total,seller,note) VALUES(?,?,?,?,?,?,?,?,?,?)',(s(d.get('date')),mid,s(d.get('material_name')),s(d.get('material_type')),q,s(d.get('unit')),rate,total,s(d.get('seller')),s(d.get('note')))); c.commit(); c.close(); return jsonify(ok=True,total=total,material_id=mid)

@app.post('/api/material_use')
def add_use():
    d=request.json; mat=s(d.get('material_name')); unit=s(d.get('unit')); q=f(d.get('qty')); uid=next_id('USE','material_use','use_id')
    rem=scalar('''SELECT SUM(qty)-COALESCE((SELECT SUM(qty) FROM material_use WHERE material_name=? AND unit=?),0) FROM purchases WHERE material_name=? AND unit=?''',(mat,unit,mat,unit))
    if q<=0 or q>rem+1e-9:return jsonify(error=f'Only {rem:g} {unit} of {mat} is available.'),400
    purchased_qty=scalar('SELECT SUM(qty) FROM purchases WHERE material_name=? AND unit=?',(mat,unit))
    purchased_total=scalar('SELECT SUM(total) FROM purchases WHERE material_name=? AND unit=?',(mat,unit))
    rate=(purchased_total/purchased_qty) if purchased_qty else 0
    amount=round(q*rate,2)
    c=conn(); c.execute('INSERT INTO material_use(date,use_id,material_name,qty,unit,work_type,work,amount,unit_rate,product_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(s(d.get('date')),uid,mat,q,unit,s(d.get('work_type')),s(d.get('work')),amount,rate,None)); c.commit(); c.close(); return jsonify(ok=True,use_id=uid,amount=amount,unit_rate=rate)

@app.post('/api/products')
def add_product():
    d=request.json; mids=d.get('materials',[]); pid=next_id('PROD','products','product_id'); c=conn()
    try:
        if not mids: raise ValueError('Add at least one Material Use ID.')
        material_cost=0; selected=[]
        for m in mids:
            uid=s(m.get('use_id')); r=c.execute('SELECT id,use_id,material_name,unit,qty,amount,product_id FROM material_use WHERE use_id=?',(uid,)).fetchone()
            if not r: raise ValueError(f'Material Use ID {uid} was not found.')
            if r['product_id']: raise ValueError(f'Material Use ID {uid} is already assigned to a product.')
            q=f(m.get('qty') or r['qty'])
            if abs(q-r['qty'])>1e-9: raise ValueError(f'Use the full quantity for {uid}: {r["qty"]:g} {r["unit"]}.')
            cost=round((r['amount']/r['qty'])*q,2) if r['qty'] else 0
            material_cost+=cost; selected.append((r,q,cost))
        machine_name=s(d.get('machine_name')); machine_minutes=max(0,f(d.get('machine_minutes'))); machine_rate=max(0,f(d.get('machine_rate_hour'))); machine_cost=round(machine_minutes/60*machine_rate,2)
        lp=max(0,f(d.get('labour_percent'))); pp=max(0,f(d.get('profit_percent'))); pf=max(0,f(d.get('profit_fixed')))
        labour=round((material_cost+machine_cost)*lp/100,2); base=material_cost+machine_cost+labour; profit=round(base*pp/100+pf,2); total=round(base+profit,2)
        c.execute('INSERT INTO products(date,product_name,product_id,material_ids,material_cost,machine_cost,labour_percent,labour_amount,profit_percent,profit_fixed,total_product_amount,machine_name,machine_minutes,machine_rate_hour) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(s(d.get('date')),s(d.get('product_name')),pid,','.join(r[0]['use_id'] for r in selected),round(material_cost,2),machine_cost,lp,labour,pp,pf,total,machine_name,machine_minutes,machine_rate))
        for r,q,cost in selected:
            c.execute('INSERT INTO product_materials(product_id,material_name,material_id,use_id,qty,unit,cost) VALUES(?,?,?,?,?,?,?)',(pid,r['material_name'],r['id'],r['use_id'],q,r['unit'],cost))
            c.execute('UPDATE material_use SET product_id=? WHERE id=?',(pid,r['id']))
        c.commit()
    except (ValueError,sqlite3.IntegrityError) as e: c.rollback(); return jsonify(error=str(e) or 'Product could not be saved.'),400
    finally:c.close()
    return jsonify(ok=True,total=total,material_cost=round(material_cost,2),machine_cost=machine_cost,labour=labour,profit=profit,product_id=pid)

@app.get('/api/product-options')
def product_options():
    return jsonify(rows('SELECT product_id,product_name,total_product_amount FROM products ORDER BY id DESC'))

@app.post('/api/sales')
def add_sale():
    d=request.json; q=f(d.get('qty')); rate=f(d.get('rate')); amount=round(q*rate,2); sid=next_id('SAL','sales','sale_id')
    c=conn(); c.execute('INSERT INTO sales(sale_id,date,customer,product_id,qty,rate,amount,remark,status) VALUES(?,?,?,?,?,?,?,?,?)',
        (sid,s(d.get('date')),s(d.get('customer')),s(d.get('product_id')),q,rate,amount,s(d.get('remark')),s(d.get('status')) or 'unpaid'))
    c.commit(); c.close(); return jsonify(ok=True,amount=amount,sale_id=sid)

@app.post('/api/daily_work')
def add_work():
    d=request.json; c=conn()
    task_id=s(d.get('task_id')); sales_id=s(d.get('sales_id'))
    if task_id:
        exists=c.execute('SELECT 1 FROM tasks WHERE task_id=?',(task_id,)).fetchone()
        if not exists: c.close(); return jsonify(error='Task ID not found.'),400
    if sales_id:
        exists=c.execute('SELECT 1 FROM sales WHERE sale_id=?',(sales_id,)).fetchone()
        if not exists: c.close(); return jsonify(error='Sales ID not found.'),400
    work_tag=s(d.get('work_tag')) or s(d.get('work_type'))
    c.execute('INSERT INTO daily_work(date,task_id,sales_id,work_type,work,tag,work_tag,remark) VALUES(?,?,?,?,?,?,?,?)',
              (s(d.get('date')),task_id or None,sales_id or None,work_tag,s(d.get('work')),work_tag,work_tag,s(d.get('remark'))))
    c.commit(); c.close(); return jsonify(ok=True)



EDITABLE_FIELDS={
 'purchases':['date','material_name','material_type','qty','unit','rate','seller','note'],
 'material_use':['date','material_name','qty','unit','work_type','work'],
 'products':['date','product_name','material_ids','machine_name','machine_minutes','machine_rate_hour','labour_percent','profit_percent','profit_fixed'],
 'sales':['date','customer','product_id','qty','rate','remark','status'],
 'daily_work':['date','task_id','sales_id','work_type','work','work_tag','remark'],
 'tasks':['date','title','description','priority','status','due_date','remark']
}

def stock_for(mat,unit,exclude_id=None):
    c=conn()
    pq=c.execute('SELECT COALESCE(SUM(qty),0) FROM purchases WHERE material_name=? AND unit=?',(mat,unit)).fetchone()[0] or 0
    if exclude_id:
        uq=c.execute('SELECT COALESCE(SUM(qty),0) FROM material_use WHERE material_name=? AND unit=? AND id<>?',(mat,unit,exclude_id)).fetchone()[0] or 0
    else:
        uq=c.execute('SELECT COALESCE(SUM(qty),0) FROM material_use WHERE material_name=? AND unit=?',(mat,unit)).fetchone()[0] or 0
    c.close(); return float(pq)-float(uq)

def product_rebuild(c,pid,d):
    old=c.execute('SELECT use_id FROM product_materials WHERE product_id=?',(pid,)).fetchall()
    for r in old: c.execute('UPDATE material_use SET product_id=NULL WHERE use_id=?',(r['use_id'],))
    c.execute('DELETE FROM product_materials WHERE product_id=?',(pid,))
    ids=[s(x) for x in str(d.get('material_ids','')).replace('\n',',').split(',') if s(x)]
    if not ids: raise ValueError('Add at least one Material Use ID.')
    material_cost=0; selected=[]
    for uid in ids:
        r=c.execute('SELECT id,use_id,material_name,unit,qty,amount,product_id FROM material_use WHERE use_id=?',(uid,)).fetchone()
        if not r: raise ValueError(f'Material Use ID {uid} was not found.')
        if r['product_id'] and r['product_id']!=pid: raise ValueError(f'Material Use ID {uid} is already assigned to another product.')
        cost=round(float(r['amount'] or 0),2); material_cost+=cost; selected.append((r,cost))
    machine_name=s(d.get('machine_name')); machine_minutes=max(0,f(d.get('machine_minutes'))); machine_rate=max(0,f(d.get('machine_rate_hour'))); machine_cost=round(machine_minutes/60*machine_rate,2)
    lp=max(0,f(d.get('labour_percent'))); pp=max(0,f(d.get('profit_percent'))); pf=max(0,f(d.get('profit_fixed')))
    labour=round((material_cost+machine_cost)*lp/100,2); profit=round((material_cost+machine_cost+labour)*pp/100+pf,2); total=round(material_cost+machine_cost+labour+profit,2)
    c.execute('UPDATE products SET date=?,product_name=?,material_ids=?,material_cost=?,machine_cost=?,labour_percent=?,labour_amount=?,profit_percent=?,profit_fixed=?,total_product_amount=?,machine_name=?,machine_minutes=?,machine_rate_hour=? WHERE product_id=?',(s(d.get('date')),s(d.get('product_name')),','.join(ids),round(material_cost,2),machine_cost,lp,labour,pp,pf,total,machine_name,machine_minutes,machine_rate,pid))
    for r,cost in selected:
        c.execute('INSERT INTO product_materials(product_id,material_name,material_id,use_id,qty,unit,cost) VALUES(?,?,?,?,?,?,?)',(pid,r['material_name'],r['id'],r['use_id'],r['qty'],r['unit'],cost))
        c.execute('UPDATE material_use SET product_id=? WHERE use_id=?',(pid,r['use_id']))
    return total

@app.put('/api/<table>/<int:rid>')
def edit(table,rid):
    if table not in EDITABLE_FIELDS:return jsonify(error='invalid table'),400
    d=request.json or {}; c=conn()
    try:
        r=c.execute(f'SELECT * FROM {table} WHERE id=?',(rid,)).fetchone()
        if not r: raise ValueError('Record not found.')
        if table=='purchases':
            nd=s(d.get('date')); mat=s(d.get('material_name')); unit=s(d.get('unit')); q=f(d.get('qty')); rate=f(d.get('rate'))
            if q<0 or rate<0 or not mat or not unit: raise ValueError('Please enter valid purchase details.')
            dep=c.execute('SELECT COUNT(*) FROM product_materials WHERE material_id=?',(rid,)).fetchone()[0]
            if dep: raise ValueError('This purchase is linked to product costing. Edit the product/material-use record first.')
            c.execute('UPDATE purchases SET date=?,material_name=?,material_type=?,qty=?,unit=?,rate=?,total=?,seller=?,note=? WHERE id=?',(nd,mat,s(d.get('material_type')),q,unit,rate,round(q*rate,2),s(d.get('seller')),s(d.get('note')),rid))
        elif table=='material_use':
            nd=s(d.get('date')); mat=s(d.get('material_name')); unit=s(d.get('unit')); q=f(d.get('qty'))
            if q<=0: raise ValueError('Quantity must be greater than zero.')
            if r['product_id']: raise ValueError('This Material Use ID is already used in product costing. Edit the Product first.')
            rem=stock_for(mat,unit,rid)
            if q>rem+1e-9: raise ValueError(f'Only {rem:g} {unit} of {mat} is available.')
            pq=c.execute('SELECT COALESCE(SUM(qty),0) FROM purchases WHERE material_name=? AND unit=?',(mat,unit)).fetchone()[0] or 0
            pc=c.execute('SELECT COALESCE(SUM(total),0) FROM purchases WHERE material_name=? AND unit=?',(mat,unit)).fetchone()[0] or 0
            rate=pc/pq if pq else 0; amount=round(q*rate,2)
            c.execute('UPDATE material_use SET date=?,material_name=?,qty=?,unit=?,work_type=?,work=?,amount=?,unit_rate=? WHERE id=?',(nd,mat,q,unit,s(d.get('work_type')),s(d.get('work')),amount,rate,rid))
        elif table=='products':
            product_rebuild(c,r['product_id'],d)
        elif table=='sales':
            q=f(d.get('qty')); rate=f(d.get('rate'))
            if q<=0 or rate<0: raise ValueError('Quantity/rate is invalid.')
            c.execute('UPDATE sales SET date=?,customer=?,product_id=?,qty=?,rate=?,amount=?,remark=?,status=? WHERE id=?',
                      (s(d.get('date')),s(d.get('customer')),s(d.get('product_id')),q,rate,round(q*rate,2),s(d.get('remark')),s(d.get('status')) or 'unpaid',rid))
        elif table=='daily_work':
            task_id=s(d.get('task_id')); sales_id=s(d.get('sales_id'))
            if task_id and not c.execute('SELECT 1 FROM tasks WHERE task_id=?',(task_id,)).fetchone(): raise ValueError('Task ID not found.')
            if sales_id and not c.execute('SELECT 1 FROM sales WHERE sale_id=?',(sales_id,)).fetchone(): raise ValueError('Sales ID not found.')
            work_tag=s(d.get('work_tag')) or s(d.get('work_type'))
            c.execute('UPDATE daily_work SET date=?,task_id=?,sales_id=?,work_type=?,work=?,tag=?,work_tag=?,remark=? WHERE id=?',
                      (s(d.get('date')),task_id or None,sales_id or None,work_tag,s(d.get('work')),work_tag,work_tag,s(d.get('remark')),rid))
        elif table=='tasks':
            title=s(d.get('title'))
            if not title: raise ValueError('Task title is required.')
            c.execute('UPDATE tasks SET date=?,title=?,description=?,assigned_to=?,priority=?,status=?,due_date=?,tag=?,remark=? WHERE id=?',
                      (s(d.get('date')),title,s(d.get('description')),s(d.get('assigned_to')),s(d.get('priority')) or 'Medium',
                       s(d.get('status')) or 'Pending',s(d.get('due_date')) or None,s(d.get('tag')),s(d.get('remark')),rid))

        c.commit(); return jsonify(ok=True)
    except Exception as e:
        c.rollback(); return jsonify(error=str(e)),400
    finally:c.close()

@app.delete('/api/<table>/<int:rid>')
def delete(table,rid):
    allowed={'purchases','material_use','products','sales','daily_work','tasks'}
    if table not in allowed:return jsonify(error='invalid'),400
    c=conn()
    if table=='purchases' and c.execute('SELECT COUNT(*) FROM product_materials WHERE material_id=?',(rid,)).fetchone()[0]: return jsonify(error='This purchase is used in product costing and cannot be deleted.'),400
    if table=='material_use' and c.execute('SELECT COUNT(*) FROM product_materials WHERE material_id=?',(rid,)).fetchone()[0]: return jsonify(error='This Material Use ID is used in product costing and cannot be deleted. Edit the product first.'),400
    if table=='products':
        pid=c.execute('SELECT product_id FROM products WHERE id=?',(rid,)).fetchone()
        if pid:
            c.execute('UPDATE material_use SET product_id=NULL WHERE product_id=?',(pid['product_id'],))
            c.execute('DELETE FROM product_materials WHERE product_id=?',(pid['product_id'],))
    cur=c.execute(f'DELETE FROM {table} WHERE id=?',(rid,))
    if cur.rowcount == 0:
        c.rollback(); c.close(); return jsonify(error='Record not found. It may already have been deleted.'),404
    c.commit(); c.close(); return jsonify(ok=True)

# Lightweight XLSX writer, stdlib only.
def col_letter(n):
    out=''
    while n: n,rem=divmod(n-1,26); out=chr(65+rem)+out
    return out

def make_xlsx(start='',end=''):
    tables=['purchases','material_use','products','product_materials','sales','daily_work','tasks']
    sheets=[]
    for t in tables:
        where,args=date_filter_clause(start,end,'date')
        if t=='product_materials': where,args=date_filter_clause(start,end,'(SELECT date FROM products WHERE products.product_id=product_materials.product_id)')
        data=rows(f'SELECT * FROM {t}{where} ORDER BY id',args)
        
        if data: headers=list(data[0].keys())
        else:
            cc=conn(); headers=[r['name'] for r in cc.execute(f'PRAGMA table_info({t})').fetchall()]; cc.close()
        xml=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for ri,row in enumerate([headers]+[[r.get(h,'') for h in headers] for r in data],1):
            xml.append(f'<row r="{ri}">')
            for ci,val in enumerate(row,1):
                ref=f'{col_letter(ci)}{ri}'
                if isinstance(val,(int,float)) and not isinstance(val,bool): xml.append(f'<c r="{ref}"><v>{val}</v></c>')
                else: xml.append(f'<c r="{ref}" t="inlineStr"><is><t>{html.escape(str(val if val is not None else ""))}</t></is></c>')
            xml.append('</row>')
        xml.append('</sheetData></worksheet>'); sheets.append(('xl/worksheets/sheet'+str(len(sheets)+1)+'.xml',''.join(xml)))
    wb=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rel=[]
    for i,(path,xml) in enumerate(sheets,1): wb.append(f'<sheet name="{tables[i-1]}" sheetId="{i}" r:id="rId{i}"/>'); rel.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb.append('</sheets></workbook>')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml">'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
        z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',''.join(wb)); z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(rel)+'</Relationships>')
        for path,xml in sheets:z.writestr(path,xml)
    buf.seek(0); return buf

@app.get('/download/excel')
def excel():
    start=s(request.args.get('from')); end=s(request.args.get('to')); name='fablab_management_data'+(f'_{start}_to_{end}' if start or end else '')+'.xlsx'
    return send_file(make_xlsx(start,end),as_attachment=True,download_name=name,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

init_db()
if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=True)
