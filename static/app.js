const $=s=>document.querySelector(s);
const money=n=>'₹'+Number(n||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
let cache={materials:[],purchases:[],products:[],useOptions:[],productOptions:[],tables:{}};
const TODAY=document.querySelector('#purchaseForm [name=date]').value;

function show(id,btn){document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));$('#'+id).classList.add('active');document.querySelectorAll('nav button').forEach(x=>x.classList.remove('navactive'));if(btn)btn.classList.add('navactive');
if(id==='dashboard')loadDashboard();if(id==='purchase'){load('purchases');refreshIds()}if(id==='use'){load('material_use');loadMaterials();refreshIds()}
if(id==='product'){loadProducts();refreshIds()}if(id==='sales'){load('sales');loadProductsForSale();refreshIds()}
if(id==='work'){load('daily_work');loadWorkLinks()}if(id==='tasks'){load('tasks');refreshIds()}}
async function api(url,opt){let r=await fetch(url,opt);let j=await r.json();if(!r.ok)throw Error(j.error||'Something went wrong');return j}
function toast(t){let x=$('#toast');x.textContent=t;x.style.display='block';clearTimeout(window._toast);window._toast=setTimeout(()=>x.style.display='none',3500)}
function formData(id){return Object.fromEntries(new FormData($('#'+id)).entries())}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function idToTable(id){return({purchaseTable:'purchases',useTable:'material_use',productTable:'products',salesTable:'sales',workTable:'daily_work',taskTable:'tasks'})[id]}
function cap(x){return x.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
function isMoney(c){return c.includes('amount')||c.includes('cost')||c==='rate'||c==='total'||c==='labour_amount'||c==='profit_fixed'||c==='total_product_amount'||c==='stock_value'||c==='unit_rate'}

async function refreshIds(){let d=await api('/api/ids');if($('#materialId'))$('#materialId').value=d.material_id;if($('#useId'))$('#useId').value=d.use_id;if($('#productId'))$('#productId').value=d.product_id;if($('#taskId'))$('#taskId').value=d.task_id;if($('#saleId'))$('#saleId').value=d.sale_id}
function dashPreset(type,btn){document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));btn.classList.add('active');if(type==='today'){$('#dashFrom').value=TODAY;$('#dashTo').value=TODAY}else{$('#dashFrom').value='';$('#dashTo').value=''}loadDashboard()}
async function loadDashboard(){let from=$('#dashFrom').value,to=$('#dashTo').value;if(from&&to&&from>to){toast('From date cannot be after To date.');return}let d=await api('/api/dashboard?from='+encodeURIComponent(from)+'&to='+encodeURIComponent(to));cache.materials=d.materials;$('#stockValue').textContent=money(d.materials.reduce((a,x)=>a+Number(x.stock_value||0),0));$('#purchaseTotal').textContent=money(d.purchase_total);$('#salesTotal').textContent=money(d.sales_total);$('#salesProfit').textContent=money(d.sales_profit);$('#unpaid').textContent=money(d.unpaid);let mt=Number(d.machine_time||0);$('#machineTime').textContent=mt>=60?`${(mt/60).toFixed(2)} hr`: `${mt.toFixed(1)} min`;renderStock();table('recentWork',d.recent_work,['date','task_id','sales_id','work_type','work','remark']);table('unpaidTable',d.unpaid_bills,['sale_id','date','customer','product_id','amount','status']);table('pendingTasks',d.pending_tasks,['task_id','due_date','title','priority','status']);$('#rangeExcel').href='/download/excel?from='+encodeURIComponent(from)+'&to='+encodeURIComponent(to)}
function renderStock(){let q=($('#stockSearch')?.value||'').toLowerCase();let d=cache.materials.filter(x=>(x.material_name||'').toLowerCase().includes(q));table('stockTable',d,['material_name','unit','purchased','used','remaining','stock_value'],true)}

function table(id,data,cols,moneyLast=false){let el=$('#'+id);if(!el)return;cache.tables[id]=data;if(!data.length){el.innerHTML='<tbody><tr><td class="muted">No records yet.</td></tr></tbody>';updateUseSelectedTotal();return}let action=!['stockTable','recentWork','unpaidTable','pendingTasks'].includes(id);let selectable=id==='useTable';el.innerHTML='<thead><tr>'+(selectable?'<th class="checkcol">✓</th>':'')+cols.map(c=>'<th>'+cap(c)+'</th>').join('')+(action?'<th>Actions</th>':'')+'</tr></thead><tbody>'+data.map(r=>'<tr>'+(selectable?`<td><input type="checkbox" class="use-check" value="${r.id}" data-amount="${Number(r.amount||0)}" onchange="updateUseSelectedTotal()"></td>`:'')+cols.map((c,i)=>'<td>'+((moneyLast&&i===cols.length-1)||isMoney(c)?money(r[c]):esc(r[c]))+'</td>').join('')+(action?'<td class="actions"><button type="button" class="edit" data-edit-table="'+idToTable(id)+'" data-id="'+r.id+'">Edit</button><button type="button" class="danger delete-btn" data-delete-table="'+idToTable(id)+'" data-id="'+r.id+'">Delete</button></td>':'')+'</tr>').join('')+'</tbody>';updateUseSelectedTotal()}
function filterHistory(id){let q=($('#'+id+'Search')?.value||'').toLowerCase();let data=cache.tables[id]||[];if(!q){renderCached(id);return}let filtered=data.filter(r=>Object.values(r).some(v=>String(v??'').toLowerCase().includes(q)));renderCached(id,filtered)}
function renderCached(id,data=cache.tables[id]||[]){let cols={purchaseTable:['material_id','date','material_name','material_type','qty','unit','rate','total','seller'],useTable:['use_id','date','material_name','qty','unit','unit_rate','amount','work_type','work','product_id'],productTable:['product_id','date','product_name','material_ids','machine_name','machine_minutes','machine_rate_hour','material_cost','machine_cost','labour_amount','profit_percent','profit_fixed','total_product_amount'],salesTable:['date','customer','product_id','qty','rate','amount','status','remark'],workTable:['date','task_id','sales_id','work_type','work','remark'],
taskTable:['task_id','date','title','priority','status','due_date','description','remark']}[id];table(id,data,cols)}
function updateUseSelectedTotal(){let checks=[...document.querySelectorAll('.use-check:checked')];let total=checks.reduce((a,x)=>a+Number(x.dataset.amount||0),0);let count=checks.length;let el=$('#useSelectedTotal');if(el)el.textContent=`${count} selected • ${money(total)}`}

async function load(t){let d=await api('/api/'+t);if(t==='purchases'){cache.purchases=d;renderCached('purchaseTable',d)}if(t==='material_use'){renderCached('useTable',d);loadMaterials()}if(t==='products'){cache.products=d;renderCached('productTable',d)}if(t==='sales')renderCached('salesTable',d);if(t==='tasks')renderCached('taskTable',d);if(t==='daily_work')renderCached('workTable',d);if(t==='tasks')renderCached('taskTable',d)}
async function loadMaterials(){cache.materials=await api('/api/materials');let sel=$('#useMaterial');sel.innerHTML=cache.materials.filter(x=>Number(x.remaining)>0).map(x=>`<option value="${esc(x.material_name)}" data-unit="${esc(x.unit)}">${esc(x.material_name)} — ${x.remaining} ${esc(x.unit)} available</option>`).join('');updateRemain()}
function updateRemain(){let o=$('#useMaterial')?.selectedOptions[0];if(!o){$('#remainHint').textContent='No available material in stock.';$('#useAmount').value='₹0.00';return}let m=cache.materials.find(x=>x.material_name===o.value&&x.unit===o.dataset.unit);if(m){$('#useUnit').value=m.unit;$('#remainHint').textContent=`Available stock: ${m.remaining} ${m.unit}`;updateUseCost()}}
function updateUseCost(){let o=$('#useMaterial')?.selectedOptions[0],q=Number($('#useForm [name=qty]')?.value||0);if(!o)return;let m=cache.materials.find(x=>x.material_name===o.value&&x.unit===o.dataset.unit);let rate=m&&Number(m.purchased)?Number(m.total_cost||0)/Number(m.purchased):0;$('#useAmount').value=money(q*rate)}
function updateProductMachineCharge(){let min=Number($('#productMachineMinutes')?.value||0),rate=Number($('#productMachineRate')?.value||0);if($('#productMachineCharge'))$('#productMachineCharge').value=money(min/60*rate)}

document.addEventListener('click',e=>{
  const delBtn=e.target.closest('.delete-btn');
  if(delBtn){e.preventDefault();e.stopPropagation();del(delBtn.dataset.deleteTable,Number(delBtn.dataset.id));return;}
  const editBtn=e.target.closest('[data-edit-table]');
  if(editBtn){e.preventDefault();e.stopPropagation();editRecord(editBtn.dataset.editTable,Number(editBtn.dataset.id));}
});

async function del(t,id){if(!confirm('Delete this entry?'))return;try{await api(`/api/${t}/${id}`,{method:'DELETE'});toast('Deleted successfully');load(t);if(t==='purchases'||t==='material_use'){loadMaterials();loadProducts()}if(t==='products')loadProducts();loadDashboard();refreshIds()}catch(e){toast(e.message)}}

const editFields={
 purchases:[['date','Date','date'],['material_name','Material Name','text'],['material_type','Material Type','select:Hardware|Electronic|Stationary|Stock'],['qty','Quantity','number'],['unit','Unit','select:sq.ft|sq.cm|liter'],['rate','Rate','number'],['seller','Seller Name','text'],['note','Note','text']],
 material_use:[['date','Date','date'],['material_name','Material Name','text'],['qty','Quantity','number'],['unit','Unit','select:sq.ft|sq.cm|liter'],['work_type','Work Type','select:Sell|Education|Service|Production|Project Work|Other'],['work','Work Details','textarea']],
 products:[['date','Date','date'],['product_name','Product Name','text'],['material_ids','Material Use IDs','textarea'],['machine_name','Machine','select:|Laser Cutting Machine|CNC Router|3D Printer|Vinyl Cutter|Other Machine'],['machine_minutes','Machine Time (minutes)','number'],['machine_rate_hour','Machine Rate / Hour','number'],['labour_percent','Labour %','number'],['profit_percent','Profit %','number'],['profit_fixed','Fixed Profit','number']],
 sales:[['date','Date','date'],['customer','Customer','text'],['product_id','Product ID','text'],['qty','Quantity','number'],['rate','Rate','number'],['status','Status','select:paid|unpaid'],['remark','Remark','text']],
 daily_work:[['date','Date','date'],['task_id','Task ID','text'],['sales_id','Sales ID','text'],['work_type','Work Tag','select:Teaching|Production|Other|Project Work|Service'],['work','Work Description','textarea'],['remark','Remark','text']],
 tasks:[['date','Date','date'],['title','Task Title','text'],['description','Description','textarea'],['priority','Priority','select:High|Medium|Low'],['status','Status','select:Pending|In Progress|Completed'],['due_date','Due Date','date'],['remark','Remark','text']]
};
function fieldHTML(def,val){let [name,label,type]=def;if(type.startsWith('select:')){let opts=type.slice(7).split('|');return `<label>${label}<select name="${name}">${opts.map(o=>`<option ${String(o).toLowerCase()===String(val??'').toLowerCase()?'selected':''}>${esc(o)}</option>`).join('')}</select></label>`}if(type==='textarea')return `<label>${label}<textarea name="${name}">${esc(val??'')}</textarea></label>`;return `<label>${label}<input name="${name}" type="${type}" value="${esc(val??'')}" ${type==='number'?'step="0.01" min="0"':''}></label>`}
async function editRecord(table,id){try{let data=cache.tables[{purchases:'purchaseTable',material_use:'useTable',products:'productTable',sales:'salesTable',daily_work:'workTable'}[table]]||[];let r=data.find(x=>Number(x.id)===Number(id));if(!r){let all=await api('/api/'+table);r=all.find(x=>Number(x.id)===Number(id))}if(!r)return;$('#editTitle').textContent='Edit '+cap(table);$('#editForm').innerHTML=editFields[table].map(f=>fieldHTML(f,r[f[0]])).join('')+`<div class="modal-actions"><button type="button" class="secondary" onclick="closeEdit()">Cancel</button><button class="primary">Save Changes</button></div>`;$('#editForm').dataset.table=table;$('#editForm').dataset.id=id;$('#editModal').classList.add('open')}catch(e){toast(e.message)}}
function closeEdit(){$('#editModal').classList.remove('open')}
$('#editForm').addEventListener('submit',async e=>{e.preventDefault();let f=e.currentTarget;let table=f.dataset.table,id=f.dataset.id;try{await api(`/api/${table}/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(f).entries()))});closeEdit();toast('Changes saved successfully');load(table);loadMaterials();loadProducts();loadProductsForSale();loadDashboard();refreshIds()}catch(err){toast(err.message)}});

function addMaterialRow(){let d=document.createElement('div');d.className='material-row';d.innerHTML=`<div class="pm-search"><input class="pmsearch" placeholder="Search Use ID / material name..."><select class="pmid"></select></div><span class="pmqty muted">Full use qty</span><span class="pmcost">₹0.00</span><button type="button" class="remove" onclick="this.parentElement.remove();calcProduct()">×</button><small></small>`;$('#materialsBox').appendChild(d);fillProductMaterials(d)}
async function fillProductMaterials(row){if(!cache.useOptions.length)cache.useOptions=await api('/api/product-use-options');let search=row.querySelector('.pmsearch'),sel=row.querySelector('.pmid');function render(){let q=search.value.toLowerCase();let selected=[...document.querySelectorAll('.pmid')].filter(x=>x!==sel).map(x=>x.value);let list=cache.useOptions.filter(p=>(p.use_id.toLowerCase().includes(q)||p.material_name.toLowerCase().includes(q))&&!selected.includes(p.use_id));sel.innerHTML=list.map(p=>`<option value="${esc(p.use_id)}" data-qty="${p.qty}" data-cost="${p.amount}" data-unit="${esc(p.unit)}" data-name="${esc(p.material_name)}">${esc(p.use_id)} • ${esc(p.material_name)} • ${p.qty} ${esc(p.unit)} • ${money(p.amount)}</option>`).join('');calcProduct()}search.oninput=render;sel.onchange=()=>{calcProduct();document.querySelectorAll('.pmsearch').forEach(x=>{if(x!==search)x.dispatchEvent(new Event('input'))})};render()}
function calcProduct(){let cost=0;document.querySelectorAll('.material-row').forEach(r=>{let o=r.querySelector('.pmid')?.selectedOptions[0],c=Number(o?.dataset.cost||0);cost+=c;r.querySelector('.pmcost').textContent=money(c);r.querySelector('.pmqty').textContent=o?`Qty: ${o.dataset.qty} ${o.dataset.unit}`:'Full use qty';r.querySelector('small').textContent=o?`${o.dataset.name} • ${o.textContent}`:''});let min=Number($('#productMachineMinutes')?.value||0),rate=Number($('#productMachineRate')?.value||0),machine=min/60*rate;let lp=Number(document.querySelector('[name=labour_percent]')?.value||0),pp=Number(document.querySelector('[name=profit_percent]')?.value||0),pf=Number(document.querySelector('[name=profit_fixed]')?.value||0);let labour=(cost+machine)*lp/100,profit=(cost+machine+labour)*pp/100+pf;$('#matCost').textContent=money(cost);$('#machineCost').textContent=money(machine);$('#labCost').textContent=money(labour);$('#profitCost').textContent=money(profit);$('#finalCost').textContent=money(cost+machine+labour+profit);updateProductMachineCharge()}
async function loadProducts(){cache.useOptions=await api('/api/product-use-options');await load('products');if(!document.querySelector('.material-row'))addMaterialRow()}
async function loadProductsForSale(){cache.productOptions=await api('/api/product-options');let s=$('#saleProduct');s.innerHTML=cache.productOptions.map(p=>`<option value="${esc(p.product_id)}" data-rate="${p.total_product_amount}">${esc(p.product_id)} • ${esc(p.product_name)} • ${money(p.total_product_amount)}</option>`).join('');updateSaleRate()}
function updateSaleRate(){let o=$('#saleProduct')?.selectedOptions[0];if(o)$('#saleRate').value=Number(o.dataset.rate||0).toFixed(2);updateSaleAmount()}
function updateSaleAmount(){$('#saleAmount').textContent=money(Number($('#salesForm [name=qty]').value||0)*Number($('#salesForm [name=rate]').value||0))}

$('#purchaseForm').addEventListener('input',()=>$('#purchaseTotalForm').textContent=money(Number($('#purchaseForm [name=qty]').value)*Number($('#purchaseForm [name=rate]').value)));
$('#useForm').addEventListener('input',updateUseCost);$('#productMachineMinutes').addEventListener('input',calcProduct);$('#productMachineRate').addEventListener('input',calcProduct);$('#productMachine').addEventListener('change',calcProduct);$('#useMaterial').addEventListener('change',updateRemain);$('#saleProduct').addEventListener('change',updateSaleRate);$('#salesForm').addEventListener('input',updateSaleAmount);['labour_percent','profit_percent','profit_fixed'].forEach(n=>document.querySelector('[name='+n+']')?.addEventListener('input',calcProduct));

async function loadWorkLinks(){
 try{
   let tasks=await api('/api/task-options'), sales=await api('/api/sale-options');
   let ts=$('#workTask'), ss=$('#workSale');
   if(ts) ts.innerHTML='<option value="">No task</option>'+tasks.map(x=>`<option value="${esc(x.task_id)}">${esc(x.task_id)} • ${esc(x.title)} • ${esc(x.status)}</option>`).join('');
   if(ss) ss.innerHTML='<option value="">No sale</option>'+sales.map(x=>`<option value="${esc(x.sale_id)}">${esc(x.sale_id)} • ${esc(x.customer||'Walk-in')} • ${esc(x.product_id)} • ${money(x.amount)}</option>`).join('');
 }catch(e){toast(e.message)}
}
async function submit(id,endpoint){try{let d=formData(id);if(id==='productForm')d.materials=[...document.querySelectorAll('.material-row')].map(r=>({use_id:r.querySelector('.pmid').value})).filter(x=>x.use_id);let j=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});toast(id==='purchaseForm'?`Saved ${j.material_id}`:id==='useForm'?`Saved ${j.use_id} • ${money(j.amount)}`:id==='productForm'?`Created ${j.product_id}`:id==='salesForm'?`Saved ${j.sale_id}`:id==='taskForm'?`Created ${j.task_id}`:'Saved successfully');$('#'+id).reset();if(id==='productForm'){$('#materialsBox').innerHTML='';cache.useOptions=[];addMaterialRow()}if(id==='salesForm')loadProductsForSale();show(id==='purchaseForm'?'purchase':id==='useForm'?'use':id==='productForm'?'product':id==='salesForm'?'sales':id==='taskForm'?'tasks':'work',document.querySelector('nav button.navactive'));refreshIds();loadMaterials();loadWorkLinks();loadDashboard()}catch(e){toast(e.message)}}
$('#purchaseForm').onsubmit=e=>{e.preventDefault();submit('purchaseForm','/api/purchases')};$('#useForm').onsubmit=e=>{e.preventDefault();submit('useForm','/api/material_use')};$('#productForm').onsubmit=e=>{e.preventDefault();submit('productForm','/api/products')};$('#salesForm').onsubmit=e=>{e.preventDefault();submit('salesForm','/api/sales')};
$('#taskForm').onsubmit=e=>{e.preventDefault();submit('taskForm','/api/tasks')};
$('#workForm').onsubmit=async e=>{
 e.preventDefault();
 try{
  const date=$('#workForm [name=date]').value, task_id=$('#workTask').value, sales_id=$('#workSale').value;
  const tags=[...document.querySelectorAll('[name="work_tag[]"]')], descs=[...document.querySelectorAll('[name="work_describe[]"]')];
  if(!tags.length){toast('Add at least one work entry.');return}
  for(let i=0;i<tags.length;i++){
    const work=descs[i].value.trim();
    if(!work){toast('Please enter Work Description for every row.');return}
    await api('/api/daily_work',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date,task_id,sales_id,work_type:tags[i].value,work})});
  }
  toast(tags.length===1?'Daily work saved successfully':`${tags.length} daily work entries saved successfully`);
  resetWorkRows(); load('daily_work'); loadDashboard();
 }catch(e){toast(e.message)}
};
function addWorkRow(){
 const wrap=$('#workRows'), row=document.createElement('div'); row.className='work-row';
 row.innerHTML=`<div class="field"><label>Work Tag</label><select name="work_tag[]"><option>Teaching</option><option>Production</option><option>Other</option><option>Project Work</option><option>Service</option></select></div><div class="field wide"><label>Work Description</label><textarea name="work_describe[]" required placeholder="Describe the work completed"></textarea></div><button type="button" class="remove work-remove" onclick="removeWorkRow(this)">×</button>`; wrap.appendChild(row); row.querySelector('textarea').focus();
}
function removeWorkRow(btn){const rows=document.querySelectorAll('#workRows .work-row');if(rows.length===1){rows[0].querySelector('textarea').value='';return}btn.closest('.work-row').remove()}
function resetWorkRows(){const rows=document.querySelectorAll('#workRows .work-row');rows.forEach((r,i)=>{if(i>0)r.remove()});rows[0].querySelector('textarea').value='';rows[0].querySelector('select').value='Teaching'}

function toggleDashSettings(){let x=$('#dashSettings');if(x)x.hidden=!x.hidden}
function toggleDash(key){
 const map={cards:'#dashCards',stockPanel:'#stockPanel',unpaidPanel:'#unpaidPanel',taskPanel:'#taskPanel',workPanel:'#workPanel'};
 const el=$(map[key]);if(!el)return;el.hidden=!el.hidden;
 let s=JSON.parse(localStorage.getItem('fablabDashVisibility')||'{}');s[key]=!el.hidden;localStorage.setItem('fablabDashVisibility',JSON.stringify(s));
}
function restoreDashVisibility(){
 let s=JSON.parse(localStorage.getItem('fablabDashVisibility')||'{}');
 Object.keys(s).forEach(k=>{if(s[k]===false){let map={cards:'#dashCards',stockPanel:'#stockPanel',unpaidPanel:'#unpaidPanel',taskPanel:'#taskPanel',workPanel:'#workPanel'};if($(map[k]))$(map[k]).hidden=true;}});
}

function setTheme(v){document.body.dataset.theme=v;localStorage.setItem('fablabTheme',v);$('#themeSelect').value=v}
$('#themeSelect')?.addEventListener('change',e=>setTheme(e.target.value));setTheme(localStorage.getItem('fablabTheme')||'blue');
restoreDashVisibility();$('#dashFrom').value=TODAY;$('#dashTo').value=TODAY;loadDashboard();loadMaterials();loadWorkLinks();load('purchases');refreshIds();
