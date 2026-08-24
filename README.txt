FABLAB MANAGEMENT SYSTEM - UPDATED

Main folder: fablab management system/

Files:
  data.db
  app.py
  requirements.txt
  templates/index.html
  static/style.css
  static/app.js

IMPORTANT
A normal browser cannot directly read/write SQLite data.db. app.py is the small local Flask backend that connects the professional web UI to the SQLite database. data.db stays in the same main folder.

NEW UPDATES
- Material ID is generated automatically: MAT-00001, MAT-00002, ...
- Product ID is generated automatically: PROD-00001, PROD-00002, ...
- Material Use ID is also generated automatically: USE-00001, USE-00002, ...
- Product Costing lets you search material names before selecting a purchase lot/material ID.
- Product material rows show material name, Material ID, available quantity, unit and rate.
- Dashboard supports Today, All Time, From/To date filtering.
- Dashboard date range updates sales, purchases, sales profit, unpaid bills and recent daily work.
- Excel: Download All Data exports all database tables.
- Excel: Date Range exports only records in the selected From/To period.
- Professional responsive UI with clear navigation, cards, search, stock hints and mobile layout.
- Stock validation prevents material use above available quantity.

CALCULATION RULES
1. Purchase total = quantity × rate.
2. Current remaining stock = total purchased − total material used, grouped by material name + unit.
3. Product material cost = sum(quantity used for costing × purchase-lot rate).
4. Labour amount = material cost × labour % ÷ 100.
5. Percentage profit = (material cost + labour amount) × profit % ÷ 100.
6. Fixed profit is added after percentage profit.
7. Final product price = material cost + labour + percentage profit + fixed profit.
8. Sale amount = sale quantity × sale rate.
9. Sales profit = sale amount − (product material cost + product labour amount) × sold quantity, when the matching Product ID exists.
10. Material use is rejected when requested quantity is greater than available stock.

WINDOWS SETUP
1. Install Python 3.10+.
2. Open Command Prompt in this folder.
3. Run: py -m pip install -r requirements.txt
4. Run: py app.py
5. Open: http://127.0.0.1:5000

The database file data.db is retained locally. Back it up before major changes.
