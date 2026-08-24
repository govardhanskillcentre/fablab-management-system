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
 work_type TEXT NOT NULL, work TEXT DEFAULT '', amount REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, product_name TEXT NOT NULL,
 product_id TEXT UNIQUE NOT NULL, material_ids TEXT NOT NULL DEFAULT '', material_cost REAL NOT NULL DEFAULT 0,
 labour_percent REAL NOT NULL DEFAULT 0, labour_amount REAL NOT NULL DEFAULT 0,
 profit_percent REAL NOT NULL DEFAULT 0, profit_fixed REAL NOT NULL DEFAULT 0,
 total_product_amount REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sales (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, customer TEXT DEFAULT '', product_id TEXT NOT NULL,
 qty REAL NOT NULL CHECK(qty>0), rate REAL NOT NULL CHECK(rate>=0), amount REAL NOT NULL,
 remark TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'unpaid'
);
CREATE TABLE IF NOT EXISTS daily_work (
 id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, work_type TEXT NOT NULL,
 work TEXT NOT NULL, remark TEXT DEFAULT ''
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
def index(): return render_template('index.html', today=date.today().isoformat())

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
    unpaid=scalar(f"SELECT SUM(amount) FROM sales{where + (' AND ' if where else ' WHERE ')}status='unpaid'",args)
    sales_profit=scalar(f'''SELECT SUM(s.amount-COALESCE((p.material_cost+p.labour_amount),0)*s.qty)
      FROM sales s LEFT JOIN products p ON p.product_id=s.product_id {where.replace('date','s.date')}''',args)
    work=rows(f'SELECT * FROM daily_work{where} ORDER BY id DESC LIMIT 8',args)
    purchase_total=scalar(f'SELECT SUM(total) FROM purchases{where}',args)
    return jsonify({'materials':materials,'sales_total':sales_total,'sales_profit':sales_profit,'labour':labour,'unpaid':unpaid,'purchase_total':purchase_total,'recent_work':work,'from':start,'to':end})

@app.get('/api/<table>')
def get_table(table):
    allowed={'purchases':'purchases','material_use':'material_use','products':'products','sales':'sales','daily_work':'daily_work'}
    if table not in allowed:return jsonify(error='invalid table'),400
    return jsonify(rows(f'SELECT * FROM {allowed[table]} ORDER BY id DESC'))

@app.get('/api/materials')
def materials():
    return jsonify(rows('''SELECT material_name,unit,ROUND(SUM(qty),4) purchased,
      ROUND(COALESCE((SELECT SUM(m.qty) FROM material_use m WHERE m.material_name=p.material_name AND m.unit=p.unit),0),4) used,
      ROUND(SUM(qty)-COALESCE((SELECT SUM(m.qty) FROM material_use m WHERE m.material_name=p.material_name AND m.unit=p.unit),0),4) remaining
      FROM purchases p GROUP BY material_name,unit ORDER BY material_name'''))

@app.get('/api/purchase-options')
def purchase_options():
    return jsonify(rows('''SELECT id,material_id,material_name,material_type,unit,rate,qty,date,
      ROUND((qty-COALESCE((SELECT SUM(mu.qty) FROM material_use mu WHERE mu.material_name=p.material_name AND mu.unit=p.unit),0)),4) remaining
      FROM purchases p ORDER BY id DESC'''))

@app.get('/api/ids')
def ids(): return jsonify(material_id=next_id('MAT','purchases','material_id'),product_id=next_id('PROD','products','product_id'),use_id=next_id('USE','material_use','use_id'))

@app.post('/api/purchases')
def add_purchase():
    d=request.json; q=f(d.get('qty')); rate=f(d.get('rate')); total=round(q*rate,2); mid=next_id('MAT','purchases','material_id')
    c=conn(); c.execute('INSERT INTO purchases(date,material_id,material_name,material_type,qty,unit,rate,total,seller,note) VALUES(?,?,?,?,?,?,?,?,?,?)',(s(d.get('date')),mid,s(d.get('material_name')),s(d.get('material_type')),q,s(d.get('unit')),rate,total,s(d.get('seller')),s(d.get('note')))); c.commit(); c.close(); return jsonify(ok=True,total=total,material_id=mid)

@app.post('/api/material_use')
def add_use():
    d=request.json; mat=s(d.get('material_name')); unit=s(d.get('unit')); q=f(d.get('qty')); uid=next_id('USE','material_use','use_id')
    rem=scalar('''SELECT SUM(qty)-COALESCE((SELECT SUM(qty) FROM material_use WHERE material_name=? AND unit=?),0) FROM purchases WHERE material_name=? AND unit=?''',(mat,unit,mat,unit))
    if q<=0 or q>rem+1e-9:return jsonify(error=f'Only {rem:g} {unit} of {mat} is available.'),400
    c=conn(); c.execute('INSERT INTO material_use(date,use_id,material_name,qty,unit,work_type,work,amount) VALUES(?,?,?,?,?,?,?,?)',(s(d.get('date')),uid,mat,q,unit,s(d.get('work_type')),s(d.get('work')),f(d.get('amount')))); c.commit(); c.close(); return jsonify(ok=True,use_id=uid)

@app.post('/api/products')
def add_product():
    d=request.json; mids=d.get('materials',[]); material_cost=0; pid=next_id('PROD','products','product_id'); c=conn()
    try:
        for m in mids:
            mid=int(m.get('purchase_id')); q=f(m.get('qty')); r=c.execute('SELECT id,material_name,unit,qty,total FROM purchases WHERE id=?',(mid,)).fetchone()
            if not r or q<=0: raise ValueError('Invalid material entry.')
            cost=(r['total']/r['qty'])*q if r['qty'] else 0; material_cost+=cost
        if not mids: raise ValueError('Add at least one material.')
        lp=max(0,f(d.get('labour_percent'))); pp=max(0,f(d.get('profit_percent'))); pf=max(0,f(d.get('profit_fixed')))
        labour=material_cost*lp/100; base=material_cost+labour; profit=base*pp/100+pf; total=round(base+profit,2)
        c.execute('INSERT INTO products(date,product_name,product_id,material_ids,material_cost,labour_percent,labour_amount,profit_percent,profit_fixed,total_product_amount) VALUES(?,?,?,?,?,?,?,?,?,?)',(s(d.get('date')),s(d.get('product_name')),pid,','.join(str(m.get('purchase_id')) for m in mids),round(material_cost,2),lp,round(labour,2),pp,pf,total))
        for m in mids:
            r=c.execute('SELECT id,material_name,unit,qty,total FROM purchases WHERE id=?',(int(m['purchase_id']),)).fetchone(); q=f(m['qty']); cost=(r['total']/r['qty'])*q
            c.execute('INSERT INTO product_materials(product_id,material_name,material_id,qty,unit,cost) VALUES(?,?,?,?,?,?)',(pid,r['material_name'],r['id'],q,r['unit'],round(cost,2)))
        c.commit()
    except (ValueError,sqlite3.IntegrityError) as e: c.rollback(); return jsonify(error=str(e) or 'Product could not be saved.'),400
    finally:c.close()
    return jsonify(ok=True,total=total,material_cost=round(material_cost,2),labour=round(labour,2),profit=round(profit,2),product_id=pid)

@app.post('/api/sales')
def add_sale():
    d=request.json; q=f(d.get('qty')); rate=f(d.get('rate')); amount=round(q*rate,2)
    c=conn(); c.execute('INSERT INTO sales(date,customer,product_id,qty,rate,amount,remark,status) VALUES(?,?,?,?,?,?,?,?)',(s(d.get('date')),s(d.get('customer')),s(d.get('product_id')),q,rate,amount,s(d.get('remark')),s(d.get('status')) or 'unpaid')); c.commit(); c.close(); return jsonify(ok=True,amount=amount)

@app.post('/api/daily_work')
def add_work():
    d=request.json; c=conn(); c.execute('INSERT INTO daily_work(date,work_type,work,remark) VALUES(?,?,?,?)',(s(d.get('date')),s(d.get('work_type')),s(d.get('work')),s(d.get('remark')))); c.commit(); c.close(); return jsonify(ok=True)

@app.delete('/api/<table>/<int:rid>')
def delete(table,rid):
    allowed={'purchases','material_use','products','sales','daily_work'}
    if table not in allowed:return jsonify(error='invalid'),400
    c=conn()
    if table=='purchases' and c.execute('SELECT COUNT(*) FROM product_materials WHERE material_id=?',(rid,)).fetchone()[0]: return jsonify(error='This purchase is used in product costing and cannot be deleted.'),400
    c.execute(f'DELETE FROM {table} WHERE id=?',(rid,)); c.commit(); c.close(); return jsonify(ok=True)

# Lightweight XLSX writer, stdlib only.
def col_letter(n):
    out=''
    while n: n,rem=divmod(n-1,26); out=chr(65+rem)+out
    return out

def make_xlsx(start='',end=''):
    tables=['purchases','material_use','products','product_materials','sales','daily_work']
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
