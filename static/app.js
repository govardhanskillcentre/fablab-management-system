const $=s=>document.querySelector(s); const money=n=>'₹'+Number(n||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
let cache={materials:[],purchases:[],products:[],options:[]}; const TODAY=document.querySelector('#purchaseForm [name=date]').value;
function show(id,btn){document.querySelectorAll('.page').forEach(x=>x.classList.remove('active')); $('#'+id).classList.add('active'); document.querySelectorAll('nav button').forEach(x=>x.classList.remove('navactive')); if(btn)btn.classList.add('navactive'); if(id==='dashboard')loadDashboard(); if(id==='purchase'){load('purchases');refreshIds()} if(id==='use'){load('material_use');loadMaterials();refreshIds()} if(id==='product'){loadProducts();refreshIds()} if(id==='sales')load('sales'); if(id==='work')load('daily_work')}
async function api(url,opt){let r=await fetch(url,opt);let j=await r.json();if(!r.ok)throw Error(j.error||'Something went wrong');return j}
function toast(t){let x=$('#toast');x.textContent=t;x.style.display='block';clearTimeout(window._toast);window._toast=setTimeout(()=>x.style.display='none',2800)}
function formData(id){return Object.fromEntries(new FormData($('#'+id)).entries())}
async function refreshIds(){let d=await api('/api/ids');if($('#materialId'))$('#materialId').value=d.material_id;if($('#useId'))$('#useId').value=d.use_id;if($('#productId'))$('#productId').value=d.product_id}
function dashPreset(type,btn){document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));btn.classList.add('active');if(type==='today'){let t=TODAY;$('#dashFrom').value=t;$('#dashTo').value=t}else{$('#dashFrom').value='';$('#dashTo').value=''}loadDashboard()}
async function loadDashboard(){let from=$('#dashFrom').value,to=$('#dashTo').value;let d=await api('/api/dashboard?from='+encodeURIComponent(from)+'&to='+encodeURIComponent(to));cache.materials=d.materials;$('#stockValue').textContent=money(d.materials.reduce((a,x)=>a+Number(x.stock_value||0),0));$('#purchaseTotal').textContent=money(d.purchase_total);$('#salesTotal').textContent=money(d.sales_total);$('#salesProfit').textContent=money(d.sales_profit);$('#unpaid').textContent=money(d.unpaid);renderStock();table('recentWork',d.recent_work,['date','work_type','work','remark']);$('#rangeExcel').href='/download/excel?from='+encodeURIComponent(from)+'&to='+encodeURIComponent(to)}
function renderStock(){let q=($('#stockSearch')?.value||'').toLowerCase();let d=cache.materials.filter(x=>x.material_name.toLowerCase().includes(q));table('stockTable',d,['material_name','unit','purchased','used','remaining','stock_value'],true)}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function table(id,data,cols,moneyLast=false){let el=$('#'+id);if(!data.length){el.innerHTML='<tbody><tr><td class="muted">No records yet.</td></tr></tbody>';return}let cap=x=>x.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());el.innerHTML='<thead><tr>'+cols.map(c=>'<th>'+cap(c)+'</th>').join('')+(id!=='stockTable'&&id!=='recentWork'?'<th>Action</th>':'')+'</tr></thead><tbody>'+data.map(r=>'<tr>'+cols.map((c,i)=>'<td>'+((moneyLast&&i===cols.length-1)||c.includes('amount')||c.includes('cost')||c==='rate'||c==='total'||c==='labour_amount'||c==='profit_fixed'||c==='total_product_amount'||c==='stock_value'?money(r[c]):esc(r[c]))+'</td>').join('')+(id!=='stockTable'&&id!=='recentWork'?'<td><button class="danger" onclick="del(\''+idToTable(id)+'\','+r.id+')">Delete</button></td>':'')+'</tr>').join('')+'</tbody>'}
function idToTable(id){return ({purchaseTable:'purchases',useTable:'material_use',productTable:'products',salesTable:'sales',workTable:'daily_work'})[id]}
async function load(t){let d=await api('/api/'+t); if(t==='purchases'){cache.purchases=d;table('purchaseTable',d,['material_id','date','material_name','material_type','qty','unit','rate','total','seller'])} if(t==='material_use'){table('useTable',d,['use_id','date','material_name','qty','unit','work_type','work','amount']);loadMaterials()} if(t==='products'){cache.products=d;table('productTable',d,['product_id','date','product_name','material_cost','labour_amount','profit_percent','profit_fixed','total_product_amount'])} if(t==='sales')table('salesTable',d,['date','customer','product_id','qty','rate','amount','status','remark']); if(t==='daily_work')table('workTable',d,['date','work_type','work','remark'])}
async function loadMaterials(){cache.materials=await api('/api/materials');let sel=$('#useMaterial');sel.innerHTML=cache.materials.filter(x=>Number(x.remaining)>0).map(x=>`<option value="${esc(x.material_name)}" data-unit="${esc(x.unit)}">${esc(x.material_name)} — ${x.remaining} ${esc(x.unit)} available</option>`).join('');updateRemain()}
function updateRemain(){let o=$('#useMaterial')?.selectedOptions[0];if(!o){$('#remainHint').textContent='No available material in stock.';return}let m=cache.materials.find(x=>x.material_name===o.value&&x.unit===o.dataset.unit);if(m){$('#useUnit').value=m.unit;$('#remainHint').textContent=`Available stock: ${m.remaining} ${m.unit}`}}
async function del(t,id){if(!confirm('Delete this entry?'))return;try{await api(`/api/${t}/${id}`,{method:'DELETE'});toast('Deleted successfully');if(t==='purchases'||t==='material_use')loadMaterials();load(t);if(t==='purchases')cache.purchases=await api('/api/purchases');loadDashboard()}catch(e){toast(e.message)}}
function addMaterialRow(){let d=document.createElement('div');d.className='material-row';d.innerHTML=`<div class="pm-search"><input class="pmsearch" placeholder="⌕ Search material name..."><select class="pmid"></select></div><input class="pmqty" type="number" min="0.0001" step="0.0001" placeholder="Qty"><span class="pmcost">₹0.00</span><button type="button" class="remove" onclick="this.parentElement.remove();calcProduct()">×</button><small></small>`;$('#materialsBox').appendChild(d);fillProductMaterials(d)}
async function fillProductMaterials(row){if(!cache.options.length)cache.options=await api('/api/purchase-options');let search=row.querySelector('.pmsearch'),sel=row.querySelector('.pmid');function render(){let q=search.value.toLowerCase();let list=cache.options.filter(p=>p.material_name.toLowerCase().includes(q)&&Number(p.remaining)>0);sel.innerHTML=list.map(p=>`<option value="${p.id}" data-rate="${p.rate}" data-unit="${esc(p.unit)}" data-name="${esc(p.material_name)}">${esc(p.material_name)} • ${esc(p.material_id)} • ${p.remaining} ${esc(p.unit)} @ ${money(p.rate)}</option>`).join('');calcProduct()}search.oninput=render;sel.onchange=calcProduct;row.querySelector('.pmqty').oninput=calcProduct;render()}
function calcProduct(){let cost=0;document.querySelectorAll('.material-row').forEach(r=>{let s=r.querySelector('.pmid'),q=Number(r.querySelector('.pmqty').value||0),rate=Number(s?.selectedOptions[0]?.dataset.rate||0);let c=q*rate;cost+=c;r.querySelector('.pmcost').textContent=money(c);r.querySelector('small').textContent=s?.selectedOptions[0]?`${s.selectedOptions[0].dataset.name} • ${s.selectedOptions[0].dataset.unit} • ${money(rate)}/unit`:''});let lp=Number(document.querySelector('[name=labour_percent]')?.value||0),pp=Number(document.querySelector('[name=profit_percent]')?.value||0),pf=Number(document.querySelector('[name=profit_fixed]')?.value||0);let labour=cost*lp/100,profit=(cost+labour)*pp/100+pf;$('#matCost').textContent=money(cost);$('#labCost').textContent=money(labour);$('#profitCost').textContent=money(profit);$('#finalCost').textContent=money(cost+labour+profit)}
async function loadProducts(){cache.options=await api('/api/purchase-options');await load('products');if(!document.querySelector('.material-row'))addMaterialRow()}
$('#purchaseForm').addEventListener('input',()=>$('#purchaseTotalForm').textContent=money(Number($('#purchaseForm [name=qty]').value)*Number($('#purchaseForm [name=rate]').value)));$('#salesForm').addEventListener('input',()=>$('#saleAmount').textContent=money(Number($('#salesForm [name=qty]').value)*Number($('#salesForm [name=rate]').value)));$('#useMaterial').addEventListener('change',updateRemain);['labour_percent','profit_percent','profit_fixed'].forEach(n=>document.querySelector('[name='+n+']')?.addEventListener('input',calcProduct));
async function submit(id,endpoint){try{let d=formData(id);if(id==='productForm')d.materials=[...document.querySelectorAll('.material-row')].map(r=>({purchase_id:r.querySelector('.pmid').value,qty:r.querySelector('.pmqty').value})).filter(x=>Number(x.qty)>0);let j=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});toast(id==='purchaseForm'?`Saved ${j.material_id}`:id==='useForm'?`Saved ${j.use_id}`:id==='productForm'?`Saved ${j.product_id}`:'Saved successfully');$('#'+id).reset();if(id==='productForm'){$('#materialsBox').innerHTML='';addMaterialRow();}show(id==='purchaseForm'?'purchase':id==='useForm'?'use':id==='productForm'?'product':id==='salesForm'?'sales':'work',document.querySelector('nav button.navactive'));refreshIds();loadMaterials();loadDashboard()}catch(e){toast(e.message)}}
$('#purchaseForm').onsubmit=e=>{e.preventDefault();submit('purchaseForm','/api/purchases')};$('#useForm').onsubmit=e=>{e.preventDefault();submit('useForm','/api/material_use')};$('#productForm').onsubmit=e=>{e.preventDefault();submit('productForm','/api/products')};$('#salesForm').onsubmit=e=>{e.preventDefault();submit('salesForm','/api/sales')};$('#workForm').onsubmit=e=>{e.preventDefault();submit('workForm','/api/daily_work')};
$('#dashFrom').value=TODAY;$('#dashTo').value=TODAY;loadDashboard();loadMaterials();load('purchases');refreshIds();

/* Firebase Authentication login. Existing FabLab functionality above is unchanged. */
const FIREBASE_ADMIN_EMAIL = 'admin@fablab.com';

function unlockApp(){
  const login=$('#loginScreen'),app=$('#appShell');
  if(login) login.hidden=true;
  if(app) app.hidden=false;
}

function lockApp(){
  const login=$('#loginScreen'),app=$('#appShell');
  if(app) app.hidden=true;
  if(login) login.hidden=false;
}

async function logout(){
  try{
    await firebase.auth().signOut();
  }catch(e){
    console.error('Logout error:',e);
    toast('Logout failed');
  }
}

function initLogin(){
  const form=$('#loginForm'),err=$('#loginError'),toggle=$('#togglePassword'),pass=$('#loginPassword');
  if(!form || !firebase || !firebase.auth) return;

  // Firebase controls the session. No password is stored in this source code.
  firebase.auth().onAuthStateChanged(user=>{
    if(user){
      unlockApp();
    }else{
      lockApp();
    }
  });

  form.addEventListener('submit',async e=>{
    e.preventDefault();
    const u=$('#loginUsername').value.trim().toLowerCase();
    const p=pass.value;
    err.style.display='none';

    if(!u || !p){
      err.textContent='Please enter username and password.';
      err.style.display='block';
      return;
    }

    // Keep the visible username as "admin" while Firebase uses the account email.
    const email=u==='admin' ? FIREBASE_ADMIN_EMAIL : u;

    try{
      await firebase.auth().signInWithEmailAndPassword(email,p);
      pass.value='';
    }catch(error){
      console.error('Firebase login error:',error);
      err.textContent='Invalid username or password.';
      err.style.display='block';
      pass.value='';
      pass.focus();
    }
  });

  toggle?.addEventListener('click',()=>{
    pass.type=pass.type==='password'?'text':'password';
    toggle.textContent=pass.type==='password'?'Show':'Hide';
  });
}

initLogin();
