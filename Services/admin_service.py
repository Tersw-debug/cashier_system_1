"""Admin data-access and business operations for the MyShop ERP schema.

This module targets Database.Schema.db (the encrypted SQLCipher Database wrapper),
not the legacy Database.get_connection() API.
"""
from __future__ import annotations

import hashlib
import json
import re
import os
from datetime import date, datetime
from typing import Any
from .security import PasswordHasher

from Database.Schema import db


# ---------------------------------------------------------------------------
# Safe resource browser: every query is explicit/allow-listed. The UI never
# chooses arbitrary SQL identifiers from user input.
# ---------------------------------------------------------------------------
RESOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "products": {
        "title": "المنتجات", "editable": True,
        "sql": """SELECT p.id, COALESCE(p.sku,''), p.name,
                  COALESCE(s.name,''), COALESCE(u.symbol,u.name,''),
                  COALESCE((SELECT GROUP_CONCAT(pb.barcode, ', ') FROM product_barcodes pb WHERE pb.product_id=p.id),''),
                  p.cost_price, p.sell_price,
                  COALESCE((SELECT SUM(sl.quantity) FROM stock_levels sl WHERE sl.product_id=p.id),0),
                  p.min_quantity, p.track_stock, p.is_active,  COALESCE(p.color,'') ,COALESCE(t.name,'')
             FROM products p LEFT JOIN sections s ON s.id=p.section_id
             LEFT JOIN units u ON u.id=p.unit_id LEFT JOIN tax_rates t ON t.id=p.tax_rate_id""",
        "columns": ["ID", "SKU", "اسم المنتج", "القسم", "الوحدة", "الباركود", "التكلفة (وحدة صغرى)", "سعر البيع (وحدة صغرى)", "المخزون", "حد التنبيه", "تتبع المخزون", "نشط", "اللون","الضريبة"],
        "search": ["p.sku", "p.name", "p.description", "s.name"],
    },
    "sections": {"title": "الأقسام", "editable": True,
        "sql": "SELECT id,name,COALESCE(parent_id,''),sort_order,is_active FROM sections",
        "columns": ["ID", "اسم القسم", "القسم الأب ID", "الترتيب", "نشط"], "search": ["name"]},
    "units": {"title": "وحدات القياس", "editable": True,
        "sql": "SELECT id,name,COALESCE(symbol,''),is_active FROM units",
        "columns": ["ID", "الوحدة", "الرمز", "نشط"], "search": ["name", "symbol"]},
    "product_barcodes": {"title": "باركود المنتجات", "editable": True,
        "sql": "SELECT pb.id,pb.product_id,p.name,pb.barcode,pb.is_primary FROM product_barcodes pb JOIN products p ON p.id=pb.product_id",
        "columns": ["ID", "معرف المنتج", "المنتج", "الباركود", "أساسي"], "search": ["p.name", "pb.barcode"]},
    "tax_rates": {"title": "الضرائب", "editable": True,
        "sql": "SELECT id,name,rate_bp,printf('%.2f%%',rate_bp/100.0),is_active FROM tax_rates",
        "columns": ["ID", "الاسم", "النقاط الأساسية", "النسبة", "نشط"], "search": ["name"]},
    "partners": {"title": "العملاء والموردون", "editable": True,
        "sql": "SELECT id,name,COALESCE(phone,''),COALESCE(email,''),is_customer,is_supplier,credit_limit,is_active FROM partners",
        "columns": ["ID", "الاسم", "الهاتف", "البريد", "عميل", "مورد", "حد الائتمان (وحدة صغرى)", "نشط"], "search": ["name", "phone", "phone2", "email", "tax_number"]},
    "customer_balances": {"title": "أرصدة العملاء", "editable": False,
        "sql": "SELECT partner_id,name,balance FROM v_customer_balances", "columns": ["معرف الشريك", "العميل", "الرصيد (وحدة صغرى)"], "search": ["name"]},
    "supplier_balances": {"title": "أرصدة الموردين", "editable": False,
        "sql": "SELECT partner_id,name,balance FROM v_supplier_balances", "columns": ["معرف الشريك", "المورد", "الرصيد (وحدة صغرى)"], "search": ["name"]},
    "warehouses": {"title": "المخازن", "editable": True,
        "sql": "SELECT id,name,COALESCE(code,''),COALESCE(address,''),is_default,is_active FROM warehouses",
        "columns": ["ID", "اسم المخزن", "الكود", "العنوان", "افتراضي", "نشط"], "search": ["name", "code", "address"]},
    "low_stock_products": {"title": "الأصناف منخفضة المخزون", "editable": False,
        "sql": "SELECT * FROM (SELECT p.id AS id,p.sku AS sku,p.name AS product_name,COALESCE((SELECT SUM(sl.quantity) FROM stock_levels sl WHERE sl.product_id=p.id),0) AS available,p.min_quantity AS min_quantity FROM products p WHERE p.track_stock=1 AND p.is_active=1 AND COALESCE((SELECT SUM(sl.quantity) FROM stock_levels sl WHERE sl.product_id=p.id),0)<=p.min_quantity) AS q",
        "columns": ["ID", "SKU", "المنتج", "المتاح", "حد التنبيه"], "search": ["q.sku", "q.product_name"]},
    "stock_valuation": {"title": "تقييم تقريبي للمخزون", "editable": False,
        "sql": "SELECT * FROM (SELECT p.id AS id,p.name AS product_name,COALESCE(SUM(sl.quantity),0) AS quantity,p.cost_price AS unit_cost,ROUND(COALESCE(SUM(sl.quantity),0)*p.cost_price) AS approximate_value FROM products p LEFT JOIN stock_levels sl ON sl.product_id=p.id WHERE p.track_stock=1 GROUP BY p.id,p.name,p.cost_price) AS q",
        "columns": ["ID", "المنتج", "الكمية", "تكلفة الوحدة", "قيمة تقريبية"], "search": ["q.product_name"]},
    "stock_levels": {"title": "أرصدة المخزون حسب المخزن", "editable": False,
        "sql": "SELECT sl.product_id,p.name,sl.warehouse_id,w.name,sl.quantity FROM stock_levels sl JOIN products p ON p.id=sl.product_id JOIN warehouses w ON w.id=sl.warehouse_id",
        "columns": ["معرف المنتج", "المنتج", "معرف المخزن", "المخزن", "الكمية"], "search": ["p.name", "w.name", "p.sku"]},
    "stock_movements": {"title": "دفتر حركة المخزون", "editable": False,
        "sql": "SELECT sm.id,sm.created_at,p.name,w.name,sm.movement_type,sm.quantity_change,COALESCE(sm.unit_cost,''),COALESCE(sm.reference_type,''),COALESCE(sm.reference_id,''),COALESCE(sm.note,'') FROM stock_movements sm JOIN products p ON p.id=sm.product_id JOIN warehouses w ON w.id=sm.warehouse_id",
        "columns": ["ID", "التاريخ", "المنتج", "المخزن", "نوع الحركة", "تغير الكمية", "التكلفة (وحدة صغرى)", "نوع المرجع", "معرف المرجع", "ملاحظة"], "search": ["p.name", "w.name", "sm.movement_type", "sm.note"]},
    "stock_transfer_items": {"title": "بنود تحويلات المخزون", "editable": False,
        "sql": "SELECT sti.id,st.number,p.name,sti.quantity FROM stock_transfer_items sti JOIN stock_transfers st ON st.id=sti.transfer_id JOIN products p ON p.id=sti.product_id",
        "columns": ["ID", "رقم التحويل", "المنتج", "الكمية"], "search": ["st.number", "p.name"]},
    "stock_transfers": {"title": "تحويلات المخزون", "editable": False,
        "sql": "SELECT st.id,st.number,w1.name,w2.name,st.status,st.created_at,COALESCE(st.note,'') FROM stock_transfers st JOIN warehouses w1 ON w1.id=st.from_warehouse_id JOIN warehouses w2 ON w2.id=st.to_warehouse_id",
        "columns": ["ID", "رقم التحويل", "من مخزن", "إلى مخزن", "الحالة", "التاريخ", "ملاحظة"], "search": ["st.number", "w1.name", "w2.name", "st.status"]},
    "purchase_orders": {"title": "أوامر الشراء", "editable": False,
        "sql": "SELECT po.id,po.number,p.name,po.order_date,COALESCE(po.expected_date,''),po.status,po.total,COALESCE(po.note,'') FROM purchase_orders po JOIN partners p ON p.id=po.supplier_id",
        "columns": ["ID", "رقم الأمر", "المورد", "التاريخ", "متوقع", "الحالة", "الإجمالي (وحدة صغرى)", "ملاحظة"], "search": ["po.number", "p.name", "po.status"]},
    "purchase_order_items": {"title": "بنود أوامر الشراء", "editable": False,
        "sql": "SELECT poi.id,po.number,p.name,poi.quantity,poi.received_quantity,poi.unit_cost FROM purchase_order_items poi JOIN purchase_orders po ON po.id=poi.order_id JOIN products p ON p.id=poi.product_id",
        "columns": ["ID", "رقم الأمر", "المنتج", "الكمية", "المستلم", "تكلفة الوحدة"], "search": ["po.number", "p.name"]},
    "purchase_invoices": {"title": "فواتير الشراء", "editable": False,
        "sql": "SELECT i.id,i.number,i.invoice_type,p.name,w.name,i.invoice_date,i.status,i.subtotal,i.tax_total,i.discount,i.total,COALESCE((SELECT SUM(a.amount) FROM payment_allocations a WHERE a.document_type='PURCHASE_INVOICE' AND a.document_id=i.id),0) FROM purchase_invoices i JOIN partners p ON p.id=i.supplier_id JOIN warehouses w ON w.id=i.warehouse_id",
        "columns": ["ID", "رقم الفاتورة", "النوع", "المورد", "المخزن", "التاريخ", "الحالة", "قبل الضريبة", "الضريبة", "الخصم", "الإجمالي", "المدفوع"], "search": ["i.number", "p.name", "i.status"]},
    "purchase_invoice_items": {"title": "بنود فواتير الشراء", "editable": False,
        "sql": "SELECT pii.id,pi.number,pii.product_name,pii.quantity,pii.unit_cost,pii.line_discount,pii.tax_rate_bp,pii.tax_amount,pii.line_total FROM purchase_invoice_items pii JOIN purchase_invoices pi ON pi.id=pii.invoice_id",
        "columns": ["ID", "رقم الفاتورة", "المنتج", "الكمية", "تكلفة الوحدة", "الخصم", "الضريبة bp", "مبلغ الضريبة", "الإجمالي"], "search": ["pi.number", "pii.product_name"]},
    "sales": {"title": "المبيعات والمرتجعات", "editable": False,
        "sql": "SELECT s.id,s.number,s.sale_type,COALESCE(p.name,'عميل نقدي'),w.name,s.sold_at,s.status,s.subtotal,s.tax_total,s.discount,s.total,COALESCE((SELECT SUM(a.amount) FROM payment_allocations a WHERE a.document_type='SALE' AND a.document_id=s.id),0) FROM sales s LEFT JOIN partners p ON p.id=s.customer_id JOIN warehouses w ON w.id=s.warehouse_id",
        "columns": ["ID", "رقم الفاتورة", "النوع", "العميل", "المخزن", "التاريخ", "الحالة", "قبل الضريبة", "الضريبة", "الخصم", "الإجمالي", "المدفوع"], "search": ["s.number", "p.name", "s.status"]},
    "sale_items": {"title": "بنود البيع", "editable": False,
        "sql": "SELECT si.id,s.number,si.product_name,si.quantity,si.unit_price,si.unit_cost,si.line_discount,si.tax_amount,si.line_total FROM sale_items si JOIN sales s ON s.id=si.sale_id",
        "columns": ["ID", "رقم البيع", "المنتج", "الكمية", "سعر الوحدة", "التكلفة", "الخصم", "الضريبة", "الإجمالي"], "search": ["s.number", "si.product_name"]},
    "payment_methods": {"title": "طرق الدفع", "editable": True,
        "sql": "SELECT pm.id,pm.name,pm.kind,pm.is_active,COALESCE(a.code || ' - ' || a.name,'') FROM payment_methods pm LEFT JOIN accounts a ON a.id=pm.account_id",
        "columns": ["ID", "الاسم", "النوع", "نشط", "حساب الأستاذ"], "search": ["pm.name", "pm.kind"]},
    "cash_shifts": {"title": "ورديات الخزينة", "editable": False,
        "sql": "SELECT cs.id,u.username,cs.opened_at,COALESCE(cs.closed_at,''),cs.opening_cash,COALESCE(cs.closing_cash,''),COALESCE(cs.expected_cash,''),cs.status,COALESCE(cs.note,'') FROM cash_shifts cs JOIN users u ON u.id=cs.user_id",
        "columns": ["ID", "المستخدم", "الفتح", "الإغلاق", "رصيد الفتح", "المبلغ الفعلي", "المتوقع", "الحالة", "ملاحظة"], "search": ["u.username", "cs.status", "cs.note"]},
    "payments": {"title": "المدفوعات", "editable": False,
        "sql": "SELECT py.id,py.number,py.direction,COALESCE(p.name,''),pm.name,py.amount,py.paid_at,COALESCE(py.reference,''),COALESCE(py.note,''),COALESCE((SELECT SUM(a.amount) FROM payment_allocations a WHERE a.payment_id=py.id),0) FROM payments py LEFT JOIN partners p ON p.id=py.partner_id JOIN payment_methods pm ON pm.id=py.method_id",
        "columns": ["ID", "الرقم", "الاتجاه", "الشريك", "طريقة الدفع", "المبلغ", "التاريخ", "مرجع", "ملاحظة", "الموزع"], "search": ["py.number", "p.name", "py.direction", "py.reference"]},
    "payment_allocations": {"title": "توزيع المدفوعات", "editable": False,
        "sql": "SELECT a.id,py.number,a.document_type,a.document_id,a.amount FROM payment_allocations a JOIN payments py ON py.id=a.payment_id",
        "columns": ["ID", "رقم الدفع", "نوع المستند", "معرف المستند", "المبلغ"], "search": ["py.number", "a.document_type"]},
    "accounts": {"title": "دليل الحسابات", "editable": True,
        "sql": "SELECT id,code,name,type,COALESCE(parent_id,''),is_system,is_active FROM accounts",
        "columns": ["ID", "الكود", "الحساب", "النوع", "الأب ID", "نظامي", "نشط"], "search": ["code", "name", "type"]},
    "journal_entries": {"title": "قيود اليومية", "editable": False,
        "sql": "SELECT je.id,je.number,je.entry_date,COALESCE(je.description,''),COALESCE(je.source_type,''),COALESCE(je.source_id,''),je.status,COALESCE((SELECT SUM(jl.debit) FROM journal_lines jl WHERE jl.entry_id=je.id),0),COALESCE((SELECT SUM(jl.credit) FROM journal_lines jl WHERE jl.entry_id=je.id),0) FROM journal_entries je",
        "columns": ["ID", "رقم القيد", "التاريخ", "الوصف", "المصدر", "معرف المصدر", "الحالة", "المدين", "الدائن"], "search": ["je.number", "je.description", "je.source_type", "je.status"]},
    "journal_lines": {"title": "بنود اليومية", "editable": False,
        "sql": "SELECT jl.id,je.number,a.code,a.name,COALESCE(p.name,''),jl.debit,jl.credit,COALESCE(jl.description,'') FROM journal_lines jl JOIN journal_entries je ON je.id=jl.entry_id JOIN accounts a ON a.id=jl.account_id LEFT JOIN partners p ON p.id=jl.partner_id",
        "columns": ["ID", "رقم القيد", "كود الحساب", "الحساب", "الشريك", "مدين", "دائن", "الوصف"], "search": ["je.number", "a.code", "a.name", "p.name"]},
    "unbalanced_entries": {"title": "تدقيق القيود غير المتوازنة", "editable": False,
        "sql": "SELECT entry_id,total_debit,total_credit FROM v_unbalanced_entries", "columns": ["معرف القيد", "إجمالي المدين", "إجمالي الدائن"], "search": []},
    "expenses": {"title": "المصروفات", "editable": False,
        "sql": "SELECT e.id,e.number,e.expense_date,a.name,pm.name,COALESCE(p.name,''),e.amount,COALESCE(e.description,''),COALESCE(e.journal_entry_id,'') FROM expenses e JOIN accounts a ON a.id=e.account_id JOIN payment_methods pm ON pm.id=e.method_id LEFT JOIN partners p ON p.id=e.partner_id",
        "columns": ["ID", "الرقم", "التاريخ", "حساب المصروف", "طريقة الدفع", "الشريك", "المبلغ", "الوصف", "قيد اليومية"], "search": ["e.number", "a.name", "e.description", "p.name"]},
    "departments": {"title": "الأقسام الوظيفية", "editable": True,
        "sql": "SELECT id,name,is_active FROM departments", "columns": ["ID", "القسم", "نشط"], "search": ["name"]},
    "employees": {"title": "الموظفون", "editable": True,
        "sql": "SELECT e.id,COALESCE(e.code,''),e.full_name,COALESCE(e.phone,''),COALESCE(d.name,''),e.salary_type,e.base_salary,e.is_active FROM employees e LEFT JOIN departments d ON d.id=e.department_id",
        "columns": ["ID", "الكود", "اسم الموظف", "الهاتف", "القسم", "نوع الأجر", "الأجر الأساسي", "نشط"], "search": ["e.code", "e.full_name", "e.phone", "d.name"]},
    "attendance": {"title": "الحضور والانصراف", "editable": True,
        "sql": "SELECT a.id,e.full_name,a.work_date,COALESCE(a.check_in,''),COALESCE(a.check_out,''),a.status,COALESCE(a.note,'') FROM attendance a JOIN employees e ON e.id=a.employee_id",
        "columns": ["ID", "الموظف", "التاريخ", "الحضور", "الانصراف", "الحالة", "ملاحظة"], "search": ["e.full_name", "a.work_date", "a.status"]},
    "payroll_runs": {"title": "مسيرات الرواتب", "editable": False,
        "sql": "SELECT pr.id,pr.number,pr.period_start,pr.period_end,pr.status,COALESCE(pr.journal_entry_id,''),COALESCE((SELECT SUM(ps.net_pay) FROM payslips ps WHERE ps.run_id=pr.id),0) FROM payroll_runs pr",
        "columns": ["ID", "رقم المسير", "من", "إلى", "الحالة", "قيد اليومية", "صافي الرواتب"], "search": ["pr.number", "pr.status"]},
    "payslips": {"title": "قسائم الرواتب", "editable": False,
        "sql": "SELECT ps.id,pr.number,e.full_name,ps.base_salary,ps.allowances,ps.deductions,ps.advances_deducted,ps.net_pay,COALESCE(ps.paid_at,'') FROM payslips ps JOIN payroll_runs pr ON pr.id=ps.run_id JOIN employees e ON e.id=ps.employee_id",
        "columns": ["ID", "مسير الرواتب", "الموظف", "الأساسي", "البدلات", "الخصومات", "السلف", "الصافي", "تاريخ الدفع"], "search": ["pr.number", "e.full_name"]},
    "employee_adjustments": {"title": "تسويات الموظفين", "editable": True,
        "sql": "SELECT ea.id,e.full_name,ea.kind,ea.amount,ea.effective_date,COALESCE(ea.note,''),COALESCE(ea.payslip_id,'') FROM employee_adjustments ea JOIN employees e ON e.id=ea.employee_id",
        "columns": ["ID", "الموظف", "النوع", "المبلغ", "التاريخ", "ملاحظة", "قسيمة الراتب ID"], "search": ["e.full_name", "ea.kind", "ea.note"]},
    "users": {"title": "المستخدمون", "editable": True,
        "sql": "SELECT u.id,u.username,COALESCE(u.full_name,''),r.name,u.is_active,u.must_change_password,COALESCE(u.last_login_at,'') FROM users u JOIN roles r ON r.id=u.role_id",
        "columns": ["ID", "اسم الدخول", "الاسم الكامل", "الدور", "نشط", "تغيير كلمة المرور", "آخر دخول"], "search": ["u.username", "u.full_name", "r.name"]},
    "roles": {"title": "الأدوار", "editable": True,
        "sql": "SELECT id,name,COALESCE(description,''),is_system FROM roles", "columns": ["ID", "الدور", "الوصف", "نظامي"], "search": ["name", "description"]},
    "permissions": {"title": "الصلاحيات", "editable": False,
        "sql": "SELECT id,code,COALESCE(description,'') FROM permissions", "columns": ["ID", "الكود", "الوصف"], "search": ["code", "description"]},
    "role_permissions": {"title": "صلاحيات الأدوار", "editable": False,
        "sql": "SELECT rp.role_id,r.name,p.code,p.description FROM role_permissions rp JOIN roles r ON r.id=rp.role_id JOIN permissions p ON p.id=rp.permission_id",
        "columns": ["معرف الدور", "الدور", "الصلاحية", "الوصف"], "search": ["r.name", "p.code", "p.description"]},
    "audit_log": {"title": "سجل التدقيق", "editable": False,
        "sql": "SELECT al.id,al.created_at,COALESCE(u.username,''),al.action,al.entity,COALESCE(al.entity_id,''),COALESCE(al.note,'') FROM audit_log al LEFT JOIN users u ON u.id=al.user_id",
        "columns": ["ID", "التاريخ", "المستخدم", "العملية", "الكيان", "معرف الكيان", "ملاحظة"], "search": ["u.username", "al.action", "al.entity", "al.note"]},
    "doc_sequences": {"title": "ترقيم المستندات", "editable": True,
        "sql": "SELECT name,prefix,next_number,padding FROM doc_sequences", "columns": ["الاسم", "البادئة", "الرقم التالي", "عدد الخانات"], "search": ["name", "prefix"]},
    "settings": {"title": "الإعدادات", "editable": True,
        "sql": "SELECT key,value,updated_at FROM settings", "columns": ["المفتاح", "القيمة", "آخر تحديث"], "search": ["key", "value"]},
}


# Field definition format used by the generic form renderer.
FIELD_DEFS: dict[str, list[dict[str, Any]]] = {
    "sections": [
        {"name":"name","label":"اسم القسم","required":True}, {"name":"parent_id","label":"القسم الأب ID","type":"int?"},
        {"name":"sort_order","label":"الترتيب","type":"int","default":"0"}, {"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "units": [{"name":"name","label":"اسم الوحدة","required":True},{"name":"symbol","label":"الرمز"},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "products": [
        {"name":"sku","label":"SKU"},{"name":"name","label":"اسم المنتج","required":True},{"name":"description","label":"الوصف"},
        {"name":"section_id","label":"القسم ID","type":"int?"},{"name":"unit_id","label":"الوحدة ID","type":"int?"},{"name":"color","label":"اللون (#RRGGBB)"},
        {"name":"cost_price","label":"سعر التكلفة بوحدة العملة الصغرى","type":"int","default":"0"},{"name":"sell_price","label":"سعر البيع بوحدة العملة الصغرى","type":"int","default":"0","required":True},
        {"name":"min_quantity","label":"حد التنبيه","type":"float","default":"0"},{"name":"track_stock","label":"تتبع المخزون (1/0)","type":"int","default":"1"},
        {"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"},{"name":"tax_rate_id","label":"الضريبة ID","type":"int?"}],
    "product_barcodes": [{"name":"product_id","label":"المنتج ID","type":"int","required":True},{"name":"barcode","label":"الباركود","required":True},{"name":"is_primary","label":"أساسي (1/0)","type":"int","default":"0"}],
    "tax_rates": [{"name":"name","label":"اسم الضريبة","required":True},{"name":"rate_bp","label":"النسبة بالنقاط الأساسية (14% = 1400)","type":"int","required":True},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "partners": [{"name":"name","label":"الاسم","required":True},{"name":"phone","label":"الهاتف"},{"name":"phone2","label":"هاتف إضافي"},{"name":"email","label":"البريد الإلكتروني"},{"name":"address","label":"العنوان"},{"name":"tax_number","label":"الرقم الضريبي"},{"name":"is_customer","label":"عميل (1/0)","type":"int","default":"1"},{"name":"is_supplier","label":"مورد (1/0)","type":"int","default":"0"},{"name":"credit_limit","label":"حد الائتمان بوحدة العملة الصغرى","type":"int","default":"0"},{"name":"notes","label":"ملاحظات"},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "warehouses": [{"name":"name","label":"اسم المخزن","required":True},{"name":"code","label":"الكود"},{"name":"address","label":"العنوان"},{"name":"is_default","label":"افتراضي (1/0)","type":"int","default":"0"},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "payment_methods": [{"name":"name","label":"اسم الطريقة","required":True},{"name":"kind","label":"النوع: CASH/CARD/TRANSFER/WALLET/OTHER","default":"CASH","required":True,"choice_values":["CASH","CARD","TRANSFER","WALLET","OTHER"]},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"},{"name":"account_id","label":"حساب الأستاذ ID","type":"int?"}],
    "accounts": [{"name":"code","label":"كود الحساب","required":True},{"name":"name","label":"اسم الحساب","required":True},{"name":"type","label":"النوع: ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE","required":True},{"name":"parent_id","label":"الحساب الأب ID","type":"int?"},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "departments": [{"name":"name","label":"اسم القسم","required":True},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "employees": [{"name":"code","label":"كود الموظف"},{"name":"full_name","label":"الاسم الكامل","required":True},{"name":"phone","label":"الهاتف"},{"name":"national_id","label":"الرقم القومي"},{"name":"job_title","label":"المسمى الوظيفي"},{"name":"department_id","label":"القسم ID","type":"int?"},{"name":"hire_date","label":"تاريخ التعيين YYYY-MM-DD"},{"name":"termination_date","label":"تاريخ إنهاء العمل YYYY-MM-DD"},{"name":"salary_type","label":"نوع الأجر MONTHLY/DAILY/HOURLY","default":"MONTHLY"},{"name":"base_salary","label":"الأجر الأساسي بوحدة العملة الصغرى","type":"int","default":"0"},{"name":"user_id","label":"حساب المستخدم ID (اختياري)","type":"int?"},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"}],
    "attendance": [{"name":"employee_id","label":"الموظف ID","type":"int","required":True},{"name":"work_date","label":"التاريخ YYYY-MM-DD","required":True},{"name":"check_in","label":"الحضور HH:MM"},{"name":"check_out","label":"الانصراف HH:MM"},{"name":"status","label":"PRESENT/ABSENT/LATE/LEAVE/HOLIDAY","default":"PRESENT","required":True},{"name":"note","label":"ملاحظة"}],
    "employee_adjustments": [{"name":"employee_id","label":"الموظف ID","type":"int","required":True},{"name":"kind","label":"ALLOWANCE/BONUS/DEDUCTION/ADVANCE","required":True,"choice_values":["ALLOWANCE","BONUS","DEDUCTION","ADVANCE"]},{"name":"amount","label":"المبلغ بوحدة العملة الصغرى","type":"int","required":True},{"name":"effective_date","label":"التاريخ YYYY-MM-DD","default":"today"},{"name":"note","label":"ملاحظة"}],
    "roles": [{"name":"name","label":"اسم الدور","required":True},{"name":"description","label":"الوصف"}],
    "users": [{"name":"username","label":"اسم الدخول","required":True},{"name":"password","label":"كلمة المرور (جديدة/اتركها فارغة عند التعديل)","secret":True},{"name":"full_name","label":"الاسم الكامل"},{"name":"role_id","label":"معرف الدور","type":"int","required":True},{"name":"is_active","label":"نشط (1/0)","type":"int","default":"1"},{"name":"must_change_password","label":"إجبار تغيير كلمة المرور (1/0)","type":"int","default":"1"}],
    "doc_sequences": [{"name":"name","label":"الاسم","required":True},{"name":"prefix","label":"البادئة","default":""},{"name":"next_number","label":"الرقم التالي","type":"int","default":"1"},{"name":"padding","label":"عدد الخانات","type":"int","default":"6"}],
    "settings": [{"name":"key","label":"المفتاح","required":True},{"name":"value","label":"القيمة"}],
}


def _fetch_all(sql: str, params=()):
    return db.fetch_all(sql, params)


def _fetch_one(sql: str, params=()):
    return db.fetch_one(sql, params)


def _next_number(c, sequence_name: str) -> str:
    row = c.execute("SELECT prefix,next_number,padding FROM doc_sequences WHERE name=?", (sequence_name,)).fetchone()
    if not row:
        raise ValueError(f"Missing document sequence: {sequence_name}")
    prefix, n, padding = row
    c.execute("UPDATE doc_sequences SET next_number=? WHERE name=?", (n + 1, sequence_name))
    return f"{prefix}{int(n):0{int(padding)}d}"


def _setting(c, key: str, default=None):
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def _audit(c, user_id: int | None, action: str, entity: str, entity_id=None,
           old_values=None, new_values=None, note: str | None = None):
    """Append a safe audit event in the same transaction as the business change."""
    def encode(value):
        if value is None:
            return None
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k not in {"password", "password_hash"}}
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    c.execute("INSERT INTO audit_log(user_id,action,entity,entity_id,old_values,new_values,note) VALUES(?,?,?,?,?,?,?)",
              (user_id, action, entity, int(entity_id) if isinstance(entity_id, int) else None,
               encode(old_values), encode(new_values), note or (str(entity_id) if entity_id is not None and not isinstance(entity_id, int) else None)))


def _snapshot(c, resource: str, record_id):
    if resource not in RESOURCE_CONFIG:
        return None
    if resource == "settings":
        row = c.execute("SELECT key,value FROM settings WHERE key=?", (str(record_id),)).fetchone()
        return {"key": row[0], "value": row[1]} if row else None
    pk = "name" if resource == "doc_sequences" else "id"
    cur = c.execute(f"SELECT * FROM {resource} WHERE {pk}=?", (record_id,))
    row = cur.fetchone()
    if not row:
        return None
    names = [d[0] for d in cur.description]
    result = dict(zip(names, row))
    result.pop("password_hash", None)
    return result


def _configured_account_id(c, key: str) -> int:
    """Account settings store account *codes* (e.g. 1100), not row IDs."""
    code = _setting(c, key)
    if code in (None, ""):
        raise ValueError(f"إعداد الحساب غير موجود: {key}")
    row = c.execute("SELECT id FROM accounts WHERE code=? AND is_active=1", (str(code),)).fetchone()
    if not row:
        raise ValueError(f"الحساب ذو الكود {code} غير موجود أو غير نشط (الإعداد {key})")
    return int(row[0])


def get_username_id(username: str) -> int | None:
    row = _fetch_one("SELECT id FROM users WHERE username=? COLLATE NOCASE", (username,))
    return int(row[0]) if row else None


def get_dashboard_stats() -> dict[str, Any]:
    def scalar(sql, params=()):
        row = _fetch_one(sql, params)
        return row[0] if row and row[0] is not None else 0
    return {
        "products": scalar("SELECT COUNT(*) FROM products WHERE is_active=1"),
        "stock_units": scalar("SELECT COALESCE(SUM(quantity),0) FROM stock_levels"),
        "low_stock": scalar("SELECT COUNT(*) FROM (SELECT p.id FROM products p LEFT JOIN stock_levels sl ON sl.product_id=p.id WHERE p.track_stock=1 AND p.is_active=1 GROUP BY p.id HAVING COALESCE(SUM(sl.quantity),0)<=p.min_quantity)"),
        "customers": scalar("SELECT COUNT(*) FROM partners WHERE is_customer=1 AND is_active=1"),
        "suppliers": scalar("SELECT COUNT(*) FROM partners WHERE is_supplier=1 AND is_active=1"),
        "sales_today": scalar("SELECT COALESCE(SUM(CASE WHEN sale_type='SALE' THEN total ELSE -total END),0) FROM sales WHERE status='POSTED' AND date(sold_at)=date('now','localtime')"),
        "receivables": scalar("SELECT COALESCE(SUM(balance),0) FROM v_customer_balances"),
        "payables": scalar("SELECT COALESCE(SUM(balance),0) FROM v_supplier_balances"),
        "employees": scalar("SELECT COUNT(*) FROM employees WHERE is_active=1"),
        "unbalanced": scalar("SELECT COUNT(*) FROM v_unbalanced_entries"),
    }


def list_resource(resource: str, search: str = ""):
    cfg = RESOURCE_CONFIG.get(resource)
    if not cfg:
        raise ValueError("Unknown admin resource")
    sql = cfg["sql"]
    params: list[Any] = []
    searchable = cfg.get("search", [])
    if search.strip() and searchable:
        sql += " WHERE " + " OR ".join(f"CAST({column} AS TEXT) LIKE ?" for column in searchable)
        params.extend([f"%{search.strip()}%"] * len(searchable))
    sql += " ORDER BY 1 DESC LIMIT 2000" if resource not in {"products", "sections", "units", "tax_rates", "partners", "warehouses", "accounts", "departments", "employees", "permissions", "roles", "settings"} else " ORDER BY 1 LIMIT 2000"
    return _fetch_all(sql, params)


def get_resource_record(resource: str, record_id: int):
    if resource == "settings":
        row = _fetch_one("SELECT key,value FROM settings WHERE key=?", (str(record_id),))
        if not row:
            return None
        return {"key": row[0], "value": row[1]}
    table_fields = {
        "sections": "id,name,parent_id,sort_order,is_active", "units": "id,name,symbol,is_active",
        "products": "id,sku,name,description,section_id,unit_id,color,cost_price,sell_price,min_quantity,track_stock,is_active,tax_rate_id",
        "product_barcodes": "id,product_id,barcode,is_primary", "tax_rates": "id,name,rate_bp,is_active",
        "partners": "id,name,phone,phone2,email,address,tax_number,is_customer,is_supplier,credit_limit,notes,is_active",
        "warehouses": "id,name,code,address,is_default,is_active", "payment_methods": "id,name,kind,is_active,account_id",
        "accounts": "id,code,name,type,parent_id,is_active", "departments": "id,name,is_active",
        "employees": "id,code,full_name,phone,national_id,job_title,department_id,hire_date,termination_date,salary_type,base_salary,user_id,is_active",
        "attendance": "id,employee_id,work_date,check_in,check_out,status,note",
        "employee_adjustments": "id,employee_id,kind,amount,effective_date,note,payslip_id",
        "roles": "id,name,description", "users": "id,username,password_hash,full_name,role_id,is_active,must_change_password",
        "doc_sequences": "name,prefix,next_number,padding",
    }
    fields = table_fields.get(resource)
    if not fields:
        raise ValueError("This resource is read-only")
    table = resource
    pk = "key" if resource == "settings" else ("name" if resource == "doc_sequences" else "id")
    row = _fetch_one(f"SELECT {fields} FROM {table} WHERE {pk}=?", (record_id,))
    return dict(zip(fields.split(","), row)) if row else None


def _coerce(field: dict[str, Any], raw: Any):
    value = str(raw).strip() if raw is not None else ""
    if value == "":
        if field.get("required"):
            raise ValueError(f"الحقل مطلوب: {field['label']}")
        if field.get("type") == "int?" or field.get("nullable"):
            return None
        default = field.get("default", "")
        if default == "today":
            default = date.today().isoformat()
        if default not in (None, ""):
            value = str(default)
        else:
            return None
    kind = field.get("type", "text")
    try:
        if kind in ("int", "int?"):
            return int(value)
        if kind == "float":
            number = float(value)
            if number != number or abs(number) == float("inf"):
                raise ValueError()
            return number
        return value
    except (ValueError, TypeError):
        raise ValueError(f"قيمة غير صحيحة في الحقل: {field['label']}")


def _hash_password(password: str) -> str:
    """PBKDF2 format for new admin-created users; login verification must use this format."""
    if len(password) < 10:
        raise ValueError("كلمة المرور يجب ألا تقل عن 10 أحرف")
    iterations = 600_000
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_admin_password(password: str, encoded: str) -> bool:
    if len(password) < 10:
        raise ValueError("كلمة المرور يجب ألا تقل عن 10 أحرف")
    return PasswordHasher.hash(password)


def save_entity(resource: str, values: dict[str, Any], record_id: int | str | None = None,
                user_id: int | None = None):
    fields = FIELD_DEFS.get(resource)
    if not fields:
        raise ValueError("This resource cannot be edited here")
    cooked = {f["name"]: _coerce(f, values.get(f["name"], f.get("default", ""))) for f in fields}
    if resource == "settings" and record_id is not None:
        cooked["key"] = str(record_id)
    if resource == "partners" and not (cooked.get("is_customer") or cooked.get("is_supplier")):
        raise ValueError("يجب تحديد الشريك كعميل أو مورد على الأقل")
    if resource == "products" and cooked.get("sell_price") is None:
        raise ValueError("سعر البيع مطلوب")
    if resource == "products" and record_id is not None:
        existing = _fetch_one("SELECT cost_price FROM products WHERE id=?", (record_id,))
        if existing and int(existing[0] or 0) != int(cooked.get("cost_price") or 0):
            movement_count = _fetch_one("SELECT COUNT(*) FROM stock_movements WHERE product_id=?", (record_id,))[0]
            if movement_count:
                raise ValueError("لا تعدّل تكلفة صنف له حركات مخزون؛ حدّث متوسط التكلفة عبر فاتورة شراء أو إجراء تسوية محاسبي معتمد")
    if resource == "accounts" and cooked.get("type") not in {"ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"}:
        raise ValueError("نوع الحساب غير صحيح")
    if resource == "warehouses" and record_id is not None and not cooked.get("is_default"):
        existing_warehouse = _fetch_one("SELECT is_default FROM warehouses WHERE id=?", (record_id,))
        if existing_warehouse and existing_warehouse[0]:
            raise ValueError("عيّن مخزنًا آخر كافتراضي أولًا؛ يجب الاحتفاظ بمخزن افتراضي")
    if resource == "accounts" and record_id is not None:
        existing_account = _fetch_one("SELECT code,type,is_system FROM accounts WHERE id=?", (record_id,))
        if existing_account and existing_account[2] and (cooked.get("code") != existing_account[0] or cooked.get("type") != existing_account[1]):
            raise ValueError("لا يمكن تغيير كود أو نوع حساب نظامي لأنه مستخدم في إعدادات الترحيل")
    if resource == "roles" and record_id is not None:
        existing = _fetch_one("SELECT name,is_system FROM roles WHERE id=?", (record_id,))
        if existing and existing[1] and cooked.get("name") != existing[0]:
            raise ValueError("لا يمكن تغيير اسم دور نظامي")
    if resource == "products":
        color = (cooked.get("color") or "").strip()
        if color:
            if not color.startswith("#"):
                color = "#" + color
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                raise ValueError("اللون يجب أن يكون بصيغة #RRGGBB مثل #1F6AA5")
            cooked["color"] = color.upper()
        else:
            cooked["color"] = None
    audit_payload = {k: v for k, v in cooked.items() if k not in {"password", "password_hash"}}
    with db.transaction() as c:
        old_values = _snapshot(c, resource, record_id) if record_id is not None else None
        if resource == "warehouses" and cooked.get("is_default") == 1:
            c.execute("UPDATE warehouses SET is_default=0 WHERE is_default=1")
        saved_id = _save_row(c, resource, cooked, record_id)
        _audit(c, user_id, "CREATE" if record_id is None else "UPDATE", resource,
               saved_id if isinstance(saved_id, int) else None, old_values, audit_payload,
               note=f"record={saved_id}" if not isinstance(saved_id, int) else None)
        return saved_id


def _save_row(c, resource, cooked, record_id):
    if resource == "settings":
        key = cooked.get("key")
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=datetime('now','localtime')", (key, cooked.get("value")))
        return key
    if resource == "doc_sequences":
        name = cooked.get("name")
        if record_id is None:
            c.execute("INSERT INTO doc_sequences(name,prefix,next_number,padding) VALUES(?,?,?,?)", (name, cooked.get("prefix") or "", cooked.get("next_number",1), cooked.get("padding",6)))
            return name
        c.execute("UPDATE doc_sequences SET prefix=?,next_number=?,padding=? WHERE name=?", (cooked.get("prefix") or "", cooked.get("next_number",1), cooked.get("padding",6), record_id))
        return record_id
    if resource == "users":
        password = str(cooked.pop("password", "") or "").strip()
        if record_id is None and not password:
            raise ValueError("كلمة المرور مطلوبة عند إنشاء مستخدم")
        if password:
            cooked["password_hash"] = _hash_password(password)
        else:
            cooked.pop("password_hash", None)
        if record_id is not None:
            old = c.execute("SELECT is_system FROM roles WHERE id=?", (cooked.get("role_id"),)).fetchone()
            if not old:
                raise ValueError("الدور المحدد غير موجود")
        if record_id is None:
            names = list(cooked)
            c.execute(f"INSERT INTO users ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", [cooked[n] for n in names])
            return c.lastrowid
        names = list(cooked)
        c.execute(f"UPDATE users SET {','.join(n+'=?' for n in names)} WHERE id=?", [cooked[n] for n in names] + [record_id])
        return record_id
    if resource == "accounts" and record_id is not None:
        existing = c.execute("SELECT is_system FROM accounts WHERE id=?", (record_id,)).fetchone()
        if existing and existing[0]:
            # System account codes/types are stable because services and settings refer to them.
            current = c.execute("SELECT code,type FROM accounts WHERE id=?", (record_id,)).fetchone()
            cooked.pop("code", None)
            cooked.pop("type", None)
    if record_id is None:
        names = list(cooked)
        c.execute(f"INSERT INTO {resource} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", [cooked[n] for n in names])
        return c.lastrowid
    names = list(cooked)
    c.execute(f"UPDATE {resource} SET {','.join(n+'=?' for n in names)} WHERE id=?", [cooked[n] for n in names] + [record_id])
    if c.rowcount == 0:
        raise ValueError("السجل غير موجود")
    return record_id


def deactivate_entity(resource: str, record_id: int, user_id: int | None = None):
    allowed = {"products", "sections", "units", "tax_rates", "partners", "warehouses", "payment_methods", "departments", "employees", "users", "accounts"}
    if resource not in allowed:
        raise ValueError("لا يمكن تعطيل هذا النوع من السجلات")
    if resource == "warehouses":
        row = _fetch_one("SELECT is_default FROM warehouses WHERE id=?", (record_id,))
        if row and row[0]:
            raise ValueError("لا يمكن تعطيل المخزن الافتراضي قبل تعيين مخزن افتراضي آخر")
    if resource == "accounts":
        row = _fetch_one("SELECT is_system FROM accounts WHERE id=?", (record_id,))
        if row and row[0]:
            raise ValueError("لا يمكن تعطيل حساب نظام أساسي")
    with db.transaction() as c:
        old_values = _snapshot(c, resource, record_id)
        c.execute(f"UPDATE {resource} SET is_active=0 WHERE id=?", (record_id,))
        if c.rowcount == 0:
            raise ValueError("السجل غير موجود")
        _audit(c, user_id, "DEACTIVATE", resource, int(record_id), old_values, {"is_active": 0})


def add_stock_adjustment(product_id: int, warehouse_id: int, quantity_change: float,
                         movement_type: str, unit_cost: int | None, user_id: int | None, note: str = ""):
    if quantity_change == 0:
        raise ValueError("تغير الكمية يجب ألا يساوي صفرًا")
    allowed = {"OPENING", "ADJUSTMENT", "DAMAGE"}
    if movement_type not in allowed:
        raise ValueError("نوع حركة غير مسموح للتسوية اليدوية")
    if unit_cost is not None and int(unit_cost) < 0:
        raise ValueError("تكلفة الوحدة لا يمكن أن تكون سالبة")
    if movement_type == "DAMAGE" and quantity_change > 0:
        raise ValueError("حركة التلف يجب أن تكون سالبة")
    with db.transaction() as c:
        product = c.execute("SELECT track_stock,is_active,cost_price FROM products WHERE id=?", (product_id,)).fetchone()
        if not product or not product[1]:
            raise ValueError("المنتج غير موجود أو غير نشط")
        if not product[0]:
            raise ValueError("المنتج لا يتتبع المخزون")
        wh = c.execute("SELECT is_active FROM warehouses WHERE id=?", (warehouse_id,)).fetchone()
        if not wh or not wh[0]:
            raise ValueError("المخزن غير موجود أو غير نشط")
        current_row = c.execute("SELECT quantity FROM stock_levels WHERE product_id=? AND warehouse_id=?", (product_id, warehouse_id)).fetchone()
        current = float(current_row[0]) if current_row else 0.0
        allow_negative = _setting(c, "allow_negative_stock", "0") == "1"
        if current + quantity_change < -1e-9 and not allow_negative:
            raise ValueError(f"الرصيد الحالي {current:g} ولا يسمح النظام بمخزون سالب")
        cost_per_unit = int(unit_cost if unit_cost is not None else (product[2] or 0))
        c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,unit_cost,reference_type,reference_id,user_id,note) VALUES(?,?,?,?,?,'MANUAL',NULL,?,?)",
                  (product_id, warehouse_id, movement_type, quantity_change, cost_per_unit, user_id, note or None))
        movement_id = c.lastrowid
        # Keep inventory subledger changes and GL valuation in the same transaction.
        # Opening stock is offset to equity; later adjustments/damage use the adjustment account.
        value = round(abs(float(quantity_change)) * cost_per_unit)
        if value > 0:
            inventory_id = _configured_account_id(c, "account.inventory")
            if movement_type == "OPENING":
                equity_id = _configured_account_id(c, "account.equity")
                lines = ([{"account_id": inventory_id, "debit": value, "credit": 0},
                          {"account_id": equity_id, "debit": 0, "credit": value}]
                         if quantity_change > 0 else
                         [{"account_id": equity_id, "debit": value, "credit": 0},
                          {"account_id": inventory_id, "debit": 0, "credit": value}])
            else:
                adjustment_id = _configured_account_id(c, "account.inventory_adjustment")
                lines = ([{"account_id": inventory_id, "debit": value, "credit": 0},
                          {"account_id": adjustment_id, "debit": 0, "credit": value}]
                         if quantity_change > 0 else
                         [{"account_id": adjustment_id, "debit": value, "credit": 0},
                          {"account_id": inventory_id, "debit": 0, "credit": value}])
            _create_journal(c, f"تسوية مخزون للحركة {movement_id}", "STOCK_MOVEMENT", movement_id, user_id, lines)
            if movement_type == "OPENING" and quantity_change > 0:
                total_before = c.execute("SELECT COALESCE(SUM(quantity),0) FROM stock_levels WHERE product_id=?", (product_id,)).fetchone()[0]
                if float(total_before or 0) == float(quantity_change):
                    c.execute("UPDATE products SET cost_price=? WHERE id=?", (cost_per_unit, product_id))
        _audit(c, user_id, "STOCK_MOVEMENT", "stock_movements", movement_id,
               new_values={"product_id": product_id, "warehouse_id": warehouse_id, "movement_type": movement_type, "quantity_change": quantity_change, "unit_cost": cost_per_unit, "journaled_value": value}, note=note)


def create_stock_transfer(from_warehouse_id: int, to_warehouse_id: int, items: list[dict[str, Any]], user_id: int | None, note: str = "") -> int:
    if from_warehouse_id == to_warehouse_id:
        raise ValueError("يجب أن يختلف المخزن المصدر عن الوجهة")
    if not items:
        raise ValueError("أضف صنفًا واحدًا على الأقل")
    # Combine duplicate product rows first; otherwise repeated rows could each pass
    # the available-stock check while their combined quantity exceeds stock.
    combined: dict[int, float] = {}
    for item in items:
        pid, qty = int(item["product_id"]), float(item["quantity"])
        if qty <= 0:
            raise ValueError("كمية التحويل يجب أن تكون موجبة")
        combined[pid] = combined.get(pid, 0.0) + qty
    items = [{"product_id": pid, "quantity": qty} for pid, qty in combined.items()]
    with db.transaction() as c:
        from_wh = c.execute("SELECT is_active FROM warehouses WHERE id=?", (from_warehouse_id,)).fetchone()
        to_wh = c.execute("SELECT is_active FROM warehouses WHERE id=?", (to_warehouse_id,)).fetchone()
        if not from_wh or not from_wh[0] or not to_wh or not to_wh[0]:
            raise ValueError("يجب اختيار مخزنين نشطين")
        settings_allow_negative = _setting(c, "allow_negative_stock", "0") == "1"
        for item in items:
            pid, qty = int(item["product_id"]), float(item["quantity"])
            row = c.execute("SELECT track_stock,is_active FROM products WHERE id=?", (pid,)).fetchone()
            if not row or not row[0] or not row[1]:
                raise ValueError(f"المنتج {pid} غير نشط أو لا يتتبع المخزون")
            stock = c.execute("SELECT quantity FROM stock_levels WHERE product_id=? AND warehouse_id=?", (pid, from_warehouse_id)).fetchone()
            available = float(stock[0]) if stock else 0.0
            if not settings_allow_negative and available < qty:
                raise ValueError(f"الرصيد غير كافٍ للمنتج ID {pid}: المتاح {available:g}، المطلوب {qty:g}")
        number = _next_number(c, "TRANSFER")
        c.execute("INSERT INTO stock_transfers(number,from_warehouse_id,to_warehouse_id,status,note,created_by) VALUES(?,?,?,'DRAFT',?,?)",
                  (number, from_warehouse_id, to_warehouse_id, note or None, user_id))
        transfer_id = c.lastrowid
        for item in items:
            c.execute("INSERT INTO stock_transfer_items(transfer_id,product_id,quantity) VALUES(?,?,?)",
                      (transfer_id, int(item["product_id"]), float(item["quantity"])))
        # Complete in the same transaction: transfer headers/items and both movements are atomic.
        for item in items:
            pid, qty = int(item["product_id"]), float(item["quantity"])
            c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,reference_type,reference_id,user_id,note) VALUES(?,?,'TRANSFER_OUT',?,'TRANSFER',?,?,?)",
                      (pid, from_warehouse_id, -qty, transfer_id, user_id, note or None))
            c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,reference_type,reference_id,user_id,note) VALUES(?,?,'TRANSFER_IN',?,'TRANSFER',?,?,?)",
                      (pid, to_warehouse_id, qty, transfer_id, user_id, note or None))
        c.execute("UPDATE stock_transfers SET status='COMPLETED' WHERE id=?", (transfer_id,))
        _audit(c, user_id, "COMPLETE", "stock_transfers", transfer_id,
               new_values={"number": number, "from_warehouse_id": from_warehouse_id, "to_warehouse_id": to_warehouse_id, "items": items, "status": "COMPLETED"}, note=note)
        return transfer_id


def _create_journal(c, description: str, source_type: str, source_id: int | None,
                    user_id: int | None, lines: list[dict[str, Any]], number=None, entry_date=None) -> int:
    if len(lines) < 2:
        raise ValueError("القيد يجب أن يحتوي على بندين على الأقل")
    debits = sum(int(line.get("debit", 0) or 0) for line in lines)
    credits = sum(int(line.get("credit", 0) or 0) for line in lines)
    if debits <= 0 or debits != credits:
        raise ValueError(f"القيد غير متوازن: المدين {debits}، الدائن {credits}")
    number = number or _next_number(c, "JOURNAL")
    c.execute("INSERT INTO journal_entries(number,entry_date,description,source_type,source_id,status,user_id) VALUES(?,?,?,?,?,'DRAFT',?)",
              (number, entry_date or date.today().isoformat(), description, source_type, source_id, user_id))
    entry_id = c.lastrowid
    for line in lines:
        debit = int(line.get("debit", 0) or 0)
        credit = int(line.get("credit", 0) or 0)
        if debit < 0 or credit < 0 or (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise ValueError("كل بند يجب أن يحتوي على مدين أو دائن فقط وبقيمة موجبة")
        c.execute("INSERT INTO journal_lines(entry_id,account_id,partner_id,debit,credit,description) VALUES(?,?,?,?,?,?)",
                  (entry_id, int(line["account_id"]), line.get("partner_id"), debit, credit, line.get("description") or None))
    c.execute("UPDATE journal_entries SET status='POSTED' WHERE id=?", (entry_id,))
    _audit(c, user_id, "POST", "journal_entries", entry_id,
           new_values={"number": number, "status": "POSTED", "total_debit": debits, "total_credit": credits, "source_type": source_type, "source_id": source_id})
    return entry_id


def create_manual_journal(entry_date: str, description: str, lines: list[dict[str, Any]], user_id: int | None) -> int:
    with db.transaction() as c:
        return _create_journal(c, description, "MANUAL", None, user_id, lines, entry_date=entry_date)


def reverse_manual_journal(entry_id: int, user_id: int | None, reason: str = "") -> int:
    """Reverse a posted manual journal using a new opposite entry.

    Operational entries are intentionally excluded: sales/purchase/payment corrections
    must use their document-specific return or correction workflow.
    """
    with db.transaction() as c:
        original = c.execute(
            "SELECT number,entry_date,description,source_type,status FROM journal_entries WHERE id=?",
            (entry_id,),
        ).fetchone()
        if not original:
            raise ValueError("القيد غير موجود")
        number, entry_date, description, source_type, status = original
        if status != "POSTED":
            raise ValueError("يمكن عكس القيود المرحلة فقط")
        if source_type != "MANUAL":
            raise ValueError("هذا قيد تشغيلي؛ استخدم مسار إرجاع/تصحيح المستند الأصلي")
        already_reversed = c.execute(
            "SELECT id FROM journal_entries WHERE source_type='REVERSAL' AND source_id=? LIMIT 1",
            (entry_id,),
        ).fetchone()
        if already_reversed:
            raise ValueError("تم عكس هذا القيد من قبل")
        rows = c.execute(
            "SELECT account_id,partner_id,debit,credit,description FROM journal_lines WHERE entry_id=? ORDER BY id",
            (entry_id,),
        ).fetchall()
        if len(rows) < 2:
            raise ValueError("القيد الأصلي لا يحتوي على بنود كافية لعكسه")
        inverse_lines = [
            {"account_id": row[0], "partner_id": row[1], "debit": int(row[3]),
             "credit": int(row[2]), "description": row[4]}
            for row in rows
        ]
        reversal_id = _create_journal(
            c, f"عكس {number}: {reason or description or ''}".strip(),
            "REVERSAL", entry_id, user_id, inverse_lines, entry_date=date.today().isoformat(),
        )
        c.execute("UPDATE journal_entries SET status='REVERSED' WHERE id=?", (entry_id,))
        _audit(c, user_id, "REVERSE", "journal_entries", entry_id,
               old_values={"status": "POSTED"},
               new_values={"status": "REVERSED", "reversal_entry_id": reversal_id, "reason": reason})
        return reversal_id


def record_expense(expense_date: str, account_id: int, method_id: int, amount: int,
                   user_id: int | None, description: str = "", partner_id: int | None = None,
                   shift_id: int | None = None) -> int:
    amount = int(amount)
    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    with db.transaction() as c:
        expense = c.execute("SELECT type,is_active FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not expense or expense[0] != "EXPENSE" or not expense[1]:
            raise ValueError("اختر حساب مصروف نشطًا من نوع EXPENSE")
        method = c.execute("SELECT account_id,is_active FROM payment_methods WHERE id=?", (method_id,)).fetchone()
        if not method or not method[1] or not method[0]:
            raise ValueError("طريقة الدفع غير نشطة أو لا ترتبط بحساب أستاذ")
        number = _next_number(c, "EXPENSE")
        c.execute("INSERT INTO expenses(number,expense_date,account_id,method_id,partner_id,shift_id,amount,description,user_id) VALUES(?,?,?,?,?,?,?,?,?)",
                  (number, expense_date, account_id, method_id, partner_id, shift_id, amount, description or None, user_id))
        expense_id = c.lastrowid
        entry_id = _create_journal(c, f"مصروف {number}: {description or ''}", "EXPENSE", expense_id, user_id,
                                   [{"account_id": account_id, "debit": amount, "credit": 0, "partner_id": partner_id},
                                    {"account_id": int(method[0]), "debit": 0, "credit": amount, "partner_id": partner_id}])
        c.execute("UPDATE expenses SET journal_entry_id=? WHERE id=?", (entry_id, expense_id))
        _audit(c, user_id, "CREATE", "expenses", expense_id,
               new_values={"number": number, "account_id": account_id, "method_id": method_id, "amount": amount, "partner_id": partner_id, "shift_id": shift_id, "journal_entry_id": entry_id}, note=description)
        return expense_id


def record_payment(direction: str, partner_id: int | None, method_id: int, amount: int,
                   user_id: int | None, allocations: list[dict[str, Any]] | None = None,
                   shift_id: int | None = None, reference: str = "", note: str = "") -> int:
    if direction not in {"IN", "OUT"}:
        raise ValueError("الاتجاه يجب أن يكون IN أو OUT")
    if partner_id is None:
        raise ValueError("يجب ربط الدفعة بعميل أو مورد")
    amount = int(amount)
    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    allocations = allocations or []
    if sum(int(a["amount"]) for a in allocations) > amount:
        raise ValueError("مجموع التوزيعات أكبر من مبلغ الدفع")
    seen_allocations: dict[tuple[str, int], int] = {}
    for alloc in allocations:
        key = (str(alloc["document_type"]), int(alloc["document_id"]))
        allocation_amount = int(alloc["amount"])
        if allocation_amount <= 0:
            raise ValueError("مبلغ التوزيع يجب أن يكون موجبًا")
        seen_allocations[key] = seen_allocations.get(key, 0) + allocation_amount
        if key[0] not in {"SALE", "PURCHASE_INVOICE"}:
            raise ValueError("نوع المستند غير مدعوم")
    allocations = [{"document_type": k[0], "document_id": k[1], "amount": amount_sum} for k, amount_sum in seen_allocations.items()]
    with db.transaction() as c:
        method = c.execute("SELECT account_id,is_active FROM payment_methods WHERE id=?", (method_id,)).fetchone()
        if not method or not method[1] or not method[0]:
            raise ValueError("طريقة الدفع غير نشطة أو لا ترتبط بحساب أستاذ")
        if partner_id is not None:
            partner = c.execute("SELECT is_customer,is_supplier,is_active FROM partners WHERE id=?", (partner_id,)).fetchone()
            if not partner or not partner[2]:
                raise ValueError("الشريك غير موجود أو غير نشط")
            if direction == "IN" and not partner[0]:
                raise ValueError("التحصيل يتطلب شريكًا معرفًا كعميل")
            if direction == "OUT" and not partner[1]:
                raise ValueError("السداد يتطلب شريكًا معرفًا كمورد")
        for alloc in allocations:
            doc_type, doc_id, alloc_amount = alloc["document_type"], int(alloc["document_id"]), int(alloc["amount"])
            if alloc_amount <= 0:
                raise ValueError("مبلغ التوزيع يجب أن يكون موجبًا")
            if direction == "IN" and doc_type != "SALE":
                raise ValueError("التحصيل من عميل يوزع على فواتير البيع فقط")
            if direction == "OUT" and doc_type != "PURCHASE_INVOICE":
                raise ValueError("السداد للمورد يوزع على فواتير الشراء فقط")
            if doc_type == "SALE":
                doc = c.execute("SELECT customer_id,total,status,sale_type FROM sales WHERE id=?", (doc_id,)).fetchone()
                if not doc or doc[2] != "POSTED" or doc[3] != "SALE":
                    raise ValueError(f"فاتورة البيع {doc_id} غير موجودة أو ليست فاتورة بيع أصلية مرحلة")
                if partner_id is not None and doc[0] != partner_id:
                    raise ValueError("العميل لا يطابق العميل الموجود في فاتورة البيع")
                already = c.execute("SELECT COALESCE(SUM(amount),0) FROM payment_allocations WHERE document_type='SALE' AND document_id=?", (doc_id,)).fetchone()[0]
            else:
                doc = c.execute("SELECT supplier_id,total,status,invoice_type FROM purchase_invoices WHERE id=?", (doc_id,)).fetchone()
                if not doc or doc[2] != "POSTED" or doc[3] != "PURCHASE":
                    raise ValueError(f"فاتورة الشراء {doc_id} غير موجودة أو ليست فاتورة شراء أصلية مرحلة")
                if partner_id is not None and doc[0] != partner_id:
                    raise ValueError("المورد لا يطابق المورد الموجود في فاتورة الشراء")
                already = c.execute("SELECT COALESCE(SUM(amount),0) FROM payment_allocations WHERE document_type='PURCHASE_INVOICE' AND document_id=?", (doc_id,)).fetchone()[0]
            if int(already) + alloc_amount > int(doc[1]):
                raise ValueError(f"التوزيع يتجاوز المتبقي من المستند {doc_id}")
        number = _next_number(c, "PAYMENT")
        c.execute("INSERT INTO payments(number,direction,partner_id,method_id,shift_id,amount,reference,note,user_id) VALUES(?,?,?,?,?,?,?,?,?)",
                  (number, direction, partner_id, method_id, shift_id, amount, reference or None, note or None, user_id))
        payment_id = c.lastrowid
        for alloc in allocations:
            c.execute("INSERT INTO payment_allocations(payment_id,document_type,document_id,amount) VALUES(?,?,?,?)",
                      (payment_id, alloc["document_type"], int(alloc["document_id"]), int(alloc["amount"])))
        account_cash = int(method[0])
        ar_id = _configured_account_id(c, "account.receivable")
        ap_id = _configured_account_id(c, "account.payable")
        counter_account = ar_id if direction == "IN" else ap_id
        lines = ([{"account_id": account_cash, "debit": amount, "credit": 0, "partner_id": partner_id},
                  {"account_id": counter_account, "debit": 0, "credit": amount, "partner_id": partner_id}] if direction == "IN" else
                 [{"account_id": counter_account, "debit": amount, "credit": 0, "partner_id": partner_id},
                  {"account_id": account_cash, "debit": 0, "credit": amount, "partner_id": partner_id}])
        _create_journal(c, f"حركة دفع {number}", "PAYMENT", payment_id, user_id, lines)
        _audit(c, user_id, "CREATE", "payments", payment_id,
               new_values={"number": number, "direction": direction, "partner_id": partner_id, "method_id": method_id, "amount": amount, "allocations": allocations})
        return payment_id


def open_cash_shift(user_id: int, opening_cash: int = 0, note: str = "") -> int:
    if int(opening_cash) < 0:
        raise ValueError("رصيد بداية الوردية لا يمكن أن يكون سالبًا")
    with db.transaction() as c:
        row = c.execute("SELECT id FROM cash_shifts WHERE user_id=? AND status='OPEN'", (user_id,)).fetchone()
        if row:
            raise ValueError("لديك وردية مفتوحة بالفعل")
        c.execute("INSERT INTO cash_shifts(user_id,opening_cash,note) VALUES(?,?,?)", (user_id, int(opening_cash), note or None))
        shift_id = c.lastrowid
        _audit(c, user_id, "OPEN_SHIFT", "cash_shifts", shift_id, new_values={"opening_cash": int(opening_cash), "status": "OPEN"}, note=note)
        return shift_id


def close_cash_shift(shift_id: int, closing_cash: int, user_id: int | None = None) -> int:
    closing_cash = int(closing_cash)
    if closing_cash < 0:
        raise ValueError("المبلغ الفعلي لا يمكن أن يكون سالبًا")
    with db.transaction() as c:
        shift = c.execute("SELECT opening_cash,status FROM cash_shifts WHERE id=?", (shift_id,)).fetchone()
        if not shift or shift[1] != "OPEN":
            raise ValueError("الوردية غير موجودة أو مغلقة")
        cash_methods = "SELECT id FROM payment_methods WHERE kind='CASH'"
        inbound = c.execute(f"SELECT COALESCE(SUM(amount),0) FROM payments WHERE shift_id=? AND direction='IN' AND method_id IN ({cash_methods})", (shift_id,)).fetchone()[0]
        outbound = c.execute(f"SELECT COALESCE(SUM(amount),0) FROM payments WHERE shift_id=? AND direction='OUT' AND method_id IN ({cash_methods})", (shift_id,)).fetchone()[0]
        expenses = c.execute("SELECT COALESCE(SUM(e.amount),0) FROM expenses e JOIN payment_methods pm ON pm.id=e.method_id WHERE e.shift_id=? AND pm.kind='CASH'", (shift_id,)).fetchone()[0]
        direct_sales = c.execute("SELECT COALESCE(SUM(CASE sale_type WHEN 'SALE' THEN total ELSE -total END),0) FROM sales WHERE shift_id=? AND customer_id IS NULL AND status='POSTED'", (shift_id,)).fetchone()[0]
        expected = int(shift[0]) + int(inbound) - int(outbound) - int(expenses) + int(direct_sales)
        c.execute("UPDATE cash_shifts SET closed_at=datetime('now','localtime'),closing_cash=?,expected_cash=?,status='CLOSED' WHERE id=?", (closing_cash, expected, shift_id))
        _audit(c, user_id, "CLOSE_SHIFT", "cash_shifts", shift_id,
               old_values={"status": "OPEN", "opening_cash": shift[0]}, new_values={"status": "CLOSED", "closing_cash": closing_cash, "expected_cash": expected})
        return expected


def create_purchase_order(supplier_id: int, product_id: int, quantity: float, unit_cost: int,
                          user_id: int | None, expected_date: str | None = None, note: str = "") -> int:
    if quantity <= 0 or unit_cost < 0:
        raise ValueError("الكمية يجب أن تكون موجبة والتكلفة غير سالبة")
    with db.transaction() as c:
        supplier = c.execute("SELECT is_supplier,is_active FROM partners WHERE id=?", (supplier_id,)).fetchone()
        product = c.execute("SELECT name,is_active FROM products WHERE id=?", (product_id,)).fetchone()
        if not supplier or not supplier[0] or not supplier[1]:
            raise ValueError("اختر موردًا نشطًا")
        if not product or not product[1]:
            raise ValueError("اختر منتجًا نشطًا")
        number = _next_number(c, "PURCHASE_ORDER")
        total = round(float(quantity) * int(unit_cost))
        c.execute("INSERT INTO purchase_orders(number,supplier_id,expected_date,status,total,note,created_by) VALUES(?,?,?,'DRAFT',?,?,?)",
                  (number, supplier_id, expected_date or None, total, note or None, user_id))
        order_id = c.lastrowid
        c.execute("INSERT INTO purchase_order_items(order_id,product_id,quantity,unit_cost) VALUES(?,?,?,?)", (order_id, product_id, quantity, unit_cost))
        _audit(c, user_id, "CREATE_DRAFT", "purchase_orders", order_id,
               new_values={"number": number, "supplier_id": supplier_id, "product_id": product_id, "quantity": quantity, "unit_cost": unit_cost, "total": total})
        return order_id


def create_purchase_invoice(supplier_id: int, warehouse_id: int, product_id: int, quantity: float,
                             unit_cost: int, tax_rate_bp: int | None = None, user_id: int | None = None,
                             note: str = "", post: bool = False) -> int:
    """Create a single-line purchase invoice. Posted tax is capitalized into inventory cost
    because the supplied chart has no input-VAT receivable account; add that account before
    using this workflow for recoverable input VAT accounting.
    """
    if quantity <= 0 or unit_cost < 0 or (tax_rate_bp is not None and tax_rate_bp < 0):
        raise ValueError("الكمية والتكلفة/الضريبة غير صحيحة")
    with db.transaction() as c:
        supplier = c.execute("SELECT is_supplier,is_active FROM partners WHERE id=?", (supplier_id,)).fetchone()
        product = c.execute("SELECT name,cost_price,track_stock,is_active,tax_rate_id FROM products WHERE id=?", (product_id,)).fetchone()
        warehouse = c.execute("SELECT is_active FROM warehouses WHERE id=?", (warehouse_id,)).fetchone()
        if not supplier or not supplier[0] or not supplier[1]:
            raise ValueError("اختر موردًا نشطًا")
        if not product or not product[3]:
            raise ValueError("اختر منتجًا نشطًا")
        if not product[2]:
            raise ValueError("مسار فاتورة الشراء المرحلة يدعم المنتجات التي تتبع المخزون فقط")
        if tax_rate_bp is None:
            tax_row = c.execute("SELECT rate_bp FROM tax_rates WHERE id=? AND is_active=1", (product[4],)).fetchone() if product[4] else None
            tax_rate_bp = int(tax_row[0]) if tax_row else 0
        if not warehouse or not warehouse[0]:
            raise ValueError("اختر مخزنًا نشطًا")
        subtotal = round(float(quantity) * int(unit_cost))
        tax_amount = round(subtotal * int(tax_rate_bp) / 10000)
        total = subtotal + tax_amount
        if post and total <= 0:
            raise ValueError("لا يمكن ترحيل فاتورة شراء بقيمة صفر")
        number = _next_number(c, "PURCHASE_INVOICE")
        status = "POSTED" if post else "DRAFT"
        c.execute("INSERT INTO purchase_invoices(number,supplier_id,warehouse_id,status,subtotal,tax_total,total,note,created_by) VALUES(?,?,?, ?,?,?,?, ?,?)",
                  (number, supplier_id, warehouse_id, status, subtotal, tax_amount, total, note or None, user_id))
        invoice_id = c.lastrowid
        c.execute("INSERT INTO purchase_invoice_items(invoice_id,product_id,product_name,quantity,unit_cost,tax_rate_bp,tax_amount,line_total) VALUES(?,?,?,?,?,?,?,?)",
                  (invoice_id, product_id, product[0], quantity, unit_cost, tax_rate_bp, tax_amount, total))
        if post:
            if product[2]:
                current_qty_row = c.execute("SELECT COALESCE(SUM(quantity),0) FROM stock_levels WHERE product_id=?", (product_id,)).fetchone()
                current_qty = max(0.0, float(current_qty_row[0] or 0))
                incoming_unit_cost = round(total / quantity)
                denominator = current_qty + float(quantity)
                new_cost = round((current_qty * int(product[1]) + float(quantity) * incoming_unit_cost) / denominator) if denominator > 0 else incoming_unit_cost
                c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,unit_cost,reference_type,reference_id,user_id,note) VALUES(?,?,'PURCHASE',?,?,?,?,?,?)",
                          (product_id, warehouse_id, quantity, incoming_unit_cost, "PURCHASE_INVOICE", invoice_id, user_id, note or None))
                c.execute("UPDATE products SET cost_price=? WHERE id=?", (new_cost, product_id))
            payable_id = _configured_account_id(c, "account.payable")
            inventory_id = _configured_account_id(c, "account.inventory")
            _create_journal(c, f"فاتورة شراء {number}", "PURCHASE_INVOICE", invoice_id, user_id,
                            [{"account_id": inventory_id, "debit": total, "credit": 0, "partner_id": supplier_id},
                             {"account_id": payable_id, "debit": 0, "credit": total, "partner_id": supplier_id}])
        _audit(c, user_id, "POST" if post else "CREATE_DRAFT", "purchase_invoices", invoice_id,
               new_values={"number": number, "supplier_id": supplier_id, "warehouse_id": warehouse_id, "total": total, "status": status})
        return invoice_id


def create_sale(customer_id: int | None, warehouse_id: int, product_id: int, quantity: float,
                unit_price: int, discount: int, tax_rate_bp: int | None, cashier_id: int,
                shift_id: int | None = None, note: str = "", post: bool = True) -> int:
    if quantity <= 0 or unit_price < 0 or discount < 0 or (tax_rate_bp is not None and tax_rate_bp < 0):
        raise ValueError("بيانات البيع غير صحيحة")
    with db.transaction() as c:
        product = c.execute("SELECT name,cost_price,track_stock,is_active,tax_rate_id FROM products WHERE id=?", (product_id,)).fetchone()
        warehouse = c.execute("SELECT is_active FROM warehouses WHERE id=?", (warehouse_id,)).fetchone()
        if not product or not product[3]:
            raise ValueError("اختر منتجًا نشطًا")
        if not warehouse or not warehouse[0]:
            raise ValueError("اختر مخزنًا نشطًا")
        if tax_rate_bp is None:
            tax_row = c.execute("SELECT rate_bp FROM tax_rates WHERE id=? AND is_active=1", (product[4],)).fetchone() if product[4] else None
            tax_rate_bp = int(tax_row[0]) if tax_row else 0
        if customer_id is not None:
            customer = c.execute("SELECT is_customer,is_active FROM partners WHERE id=?", (customer_id,)).fetchone()
            if not customer or not customer[0] or not customer[1]:
                raise ValueError("اختر عميلًا نشطًا")
        base = round(float(quantity) * int(unit_price))
        if discount > base:
            raise ValueError("الخصم لا يمكن أن يتجاوز قيمة البنود")
        taxable = base - discount
        tax_amount = round(taxable * int(tax_rate_bp) / 10000)
        total = taxable + tax_amount
        if post and total <= 0:
            raise ValueError("لا يمكن ترحيل عملية بيع بقيمة صفر")
        if product[2]:
            stock = c.execute("SELECT quantity FROM stock_levels WHERE product_id=? AND warehouse_id=?", (product_id, warehouse_id)).fetchone()
            available = float(stock[0]) if stock else 0.0
            if available < quantity and _setting(c, "allow_negative_stock", "0") != "1":
                raise ValueError(f"المخزون غير كافٍ: المتاح {available:g}")
        number = _next_number(c, "SALE")
        status = "POSTED" if post else "DRAFT"
        c.execute("INSERT INTO sales(number,sale_type,customer_id,warehouse_id,cashier_id,shift_id,status,subtotal,tax_total,discount,total,note) VALUES(?,'SALE',?,?,?,?,?,?,?,?,?,?)",
                  (number, customer_id, warehouse_id, cashier_id, shift_id, status, base, tax_amount, discount, total, note or None))
        sale_id = c.lastrowid
        c.execute("INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,unit_cost,line_discount,tax_rate_bp,tax_amount,line_total) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (sale_id, product_id, product[0], quantity, unit_price, product[1], discount, tax_rate_bp, tax_amount, total))
        if post and product[2]:
            c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,unit_cost,reference_type,reference_id,user_id,note) VALUES(?,?,'SALE',?,?,?,?,?,?)",
                      (product_id, warehouse_id, -quantity, product[1], "SALE", sale_id, cashier_id, note or None))
        if post:
            sales_account = _configured_account_id(c, "account.sales")
            tax_account = _configured_account_id(c, "account.tax_payable")
            ar_account = _configured_account_id(c, "account.receivable")
            cash_account = _configured_account_id(c, "account.cash")
            inv_account = _configured_account_id(c, "account.inventory")
            cogs_account = _configured_account_id(c, "account.cogs")
            receivable_or_cash = ar_account if customer_id is not None else cash_account
            lines = [{"account_id": receivable_or_cash, "debit": total, "credit": 0, "partner_id": customer_id},
                     {"account_id": sales_account, "debit": 0, "credit": taxable, "partner_id": customer_id}]
            if tax_amount:
                lines.append({"account_id": tax_account, "debit": 0, "credit": tax_amount, "partner_id": customer_id})
            cogs = round(float(quantity) * int(product[1]))
            if product[2] and cogs:
                lines.extend([{"account_id": cogs_account, "debit": cogs, "credit": 0, "partner_id": customer_id},
                              {"account_id": inv_account, "debit": 0, "credit": cogs, "partner_id": customer_id}])
            _create_journal(c, f"فاتورة بيع {number}", "SALE", sale_id, cashier_id, lines)
        _audit(c, cashier_id, "POST" if post else "CREATE_DRAFT", "sales", sale_id,
               new_values={"number": number, "customer_id": customer_id, "product_id": product_id, "quantity": quantity, "total": total, "status": status})
        return sale_id


def create_sale_return(original_sale_id: int, product_id: int, quantity: float,
                       cashier_id: int, shift_id: int | None = None, note: str = "") -> int:
    """Post a return against one product line from an existing posted sale."""
    if quantity <= 0:
        raise ValueError("كمية المرتجع يجب أن تكون موجبة")
    with db.transaction() as c:
        original = c.execute("SELECT number,customer_id,warehouse_id,status,sale_type FROM sales WHERE id=?", (original_sale_id,)).fetchone()
        if not original or original[3] != "POSTED" or original[4] != "SALE":
            raise ValueError("فاتورة البيع الأصلية غير موجودة أو ليست فاتورة بيع مرحلة")
        line = c.execute("SELECT product_name,quantity,unit_price,unit_cost,line_discount,tax_rate_bp FROM sale_items WHERE sale_id=? AND product_id=? ORDER BY id LIMIT 1", (original_sale_id, product_id)).fetchone()
        if not line:
            raise ValueError("المنتج لا يوجد ضمن الفاتورة الأصلية")
        product_name, sold_qty, unit_price, unit_cost, original_discount, tax_rate_bp = line
        already_returned = c.execute("SELECT COALESCE(SUM(si.quantity),0) FROM sale_items si JOIN sales r ON r.id=si.sale_id WHERE r.original_sale_id=? AND r.sale_type='RETURN' AND r.status='POSTED' AND si.product_id=?", (original_sale_id, product_id)).fetchone()[0]
        remaining = float(sold_qty) - float(already_returned)
        if quantity > remaining + 1e-9:
            raise ValueError(f"الكمية المتبقية للمرتجع {remaining:g} فقط")
        base = round(float(quantity) * int(unit_price))
        discount = min(base, round(int(original_discount) * float(quantity) / float(sold_qty)))
        tax_amount = round((base - discount) * int(tax_rate_bp) / 10000)
        total = base - discount + tax_amount
        if total <= 0:
            raise ValueError("لا يمكن إنشاء مرتجع بقيمة صفر")
        number = _next_number(c, "SALE_RETURN")
        c.execute("INSERT INTO sales(number,sale_type,original_sale_id,customer_id,warehouse_id,cashier_id,shift_id,status,subtotal,tax_total,discount,total,note) VALUES(?,'RETURN',?,?,?,?,?,'POSTED',?,?,?,?,?)",
                  (number, original_sale_id, original[1], original[2], cashier_id, shift_id, base, tax_amount, discount, total, note or f"مرتجع من {original[0]}"))
        return_id = c.lastrowid
        c.execute("INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,unit_cost,line_discount,tax_rate_bp,tax_amount,line_total) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (return_id, product_id, product_name, quantity, unit_price, unit_cost, discount, tax_rate_bp, tax_amount, total))
        product = c.execute("SELECT track_stock FROM products WHERE id=?", (product_id,)).fetchone()
        if product and product[0]:
            c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,unit_cost,reference_type,reference_id,user_id,note) VALUES(?,?,'SALE_RETURN',?,?,?,?,?,?)",
                      (product_id, original[2], quantity, unit_cost, "SALE", return_id, cashier_id, note or None))
        returns_account = _configured_account_id(c, "account.sales_returns")
        tax_account = _configured_account_id(c, "account.tax_payable")
        ar_account = _configured_account_id(c, "account.receivable")
        cash_account = _configured_account_id(c, "account.cash")
        lines = [{"account_id": returns_account, "debit": base-discount, "credit": 0, "partner_id": original[1]}]
        if tax_amount:
            lines.append({"account_id": tax_account, "debit": tax_amount, "credit": 0, "partner_id": original[1]})
        lines.append({"account_id": ar_account if original[1] is not None else cash_account, "debit": 0, "credit": total, "partner_id": original[1]})
        if product and product[0]:
            cogs_reversal = round(float(quantity) * int(unit_cost))
            if cogs_reversal:
                inv_account = _configured_account_id(c, "account.inventory")
                cogs_account = _configured_account_id(c, "account.cogs")
                lines.extend([{"account_id": inv_account, "debit": cogs_reversal, "credit": 0, "partner_id": original[1]},
                              {"account_id": cogs_account, "debit": 0, "credit": cogs_reversal, "partner_id": original[1]}])
        _create_journal(c, f"مرتجع بيع {number}", "SALE_RETURN", return_id, cashier_id, lines)
        _audit(c, cashier_id, "POST_RETURN", "sales", return_id,
               new_values={"number": number, "original_sale_id": original_sale_id, "product_id": product_id, "quantity": quantity, "total": total})
        return return_id


def create_purchase_return(original_invoice_id: int, product_id: int, quantity: float,
                           user_id: int | None, note: str = "") -> int:
    """Post a supplier return against a posted purchase invoice line.

    As with purchase posting, tax is included in inventory cost because the current
    chart has no separate recoverable input-VAT asset account.
    """
    if quantity <= 0:
        raise ValueError("كمية المرتجع يجب أن تكون موجبة")
    with db.transaction() as c:
        original = c.execute("SELECT number,supplier_id,warehouse_id,status,invoice_type FROM purchase_invoices WHERE id=?", (original_invoice_id,)).fetchone()
        if not original or original[3] != "POSTED" or original[4] != "PURCHASE":
            raise ValueError("فاتورة الشراء الأصلية غير موجودة أو ليست فاتورة شراء مرحلة")
        line = c.execute("SELECT product_name,quantity,unit_cost,line_discount,tax_rate_bp,tax_amount FROM purchase_invoice_items WHERE invoice_id=? AND product_id=? ORDER BY id LIMIT 1", (original_invoice_id, product_id)).fetchone()
        if not line:
            raise ValueError("المنتج لا يوجد ضمن الفاتورة الأصلية")
        product_name, purchased_qty, unit_cost, original_discount, tax_rate_bp, original_tax = line
        already_returned = c.execute("SELECT COALESCE(SUM(pii.quantity),0) FROM purchase_invoice_items pii JOIN purchase_invoices r ON r.id=pii.invoice_id WHERE r.invoice_type='RETURN' AND r.supplier_ref=? AND r.status='POSTED' AND pii.product_id=?", (original[0], product_id)).fetchone()[0]
        remaining = float(purchased_qty) - float(already_returned)
        if quantity > remaining + 1e-9:
            raise ValueError(f"الكمية المتبقية للمرتجع {remaining:g} فقط")
        base = round(float(quantity) * int(unit_cost))
        discount = min(base, round(int(original_discount) * float(quantity) / float(purchased_qty)))
        subtotal = base
        tax_amount = round((base - discount) * int(tax_rate_bp) / 10000)
        total = base - discount + tax_amount
        if total <= 0:
            raise ValueError("لا يمكن إنشاء مرتجع بقيمة صفر")
        number = _next_number(c, "PURCHASE_INVOICE")
        c.execute("INSERT INTO purchase_invoices(number,invoice_type,supplier_id,warehouse_id,supplier_ref,status,subtotal,discount,tax_total,total,note,created_by) VALUES(?,'RETURN',?,?,?,'POSTED',?,?,?,?,?,?)",
                  (number, original[1], original[2], original[0], subtotal, discount, tax_amount, total, note or f"مرتجع من {original[0]}", user_id))
        return_id = c.lastrowid
        c.execute("INSERT INTO purchase_invoice_items(invoice_id,product_id,product_name,quantity,unit_cost,line_discount,tax_rate_bp,tax_amount,line_total) VALUES(?,?,?,?,?,?,?,?,?)",
                  (return_id, product_id, product_name, quantity, unit_cost, discount, tax_rate_bp, tax_amount, total))
        product = c.execute("SELECT track_stock FROM products WHERE id=?", (product_id,)).fetchone()
        if product and product[0]:
            stock = c.execute("SELECT quantity FROM stock_levels WHERE product_id=? AND warehouse_id=?", (product_id, original[2])).fetchone()
            available = float(stock[0]) if stock else 0.0
            if available < quantity and _setting(c, "allow_negative_stock", "0") != "1":
                raise ValueError(f"المخزون المتاح {available:g} لا يكفي لمرتجع المورد")
            c.execute("INSERT INTO stock_movements(product_id,warehouse_id,movement_type,quantity_change,unit_cost,reference_type,reference_id,user_id,note) VALUES(?,?,'PURCHASE_RETURN',?,?,?,?,?,?)",
                      (product_id, original[2], -quantity, unit_cost, "PURCHASE_INVOICE", return_id, user_id, note or None))
        payable_id = _configured_account_id(c, "account.payable")
        inventory_id = _configured_account_id(c, "account.inventory")
        _create_journal(c, f"مرتجع شراء {number}", "PURCHASE_RETURN", return_id, user_id,
                        [{"account_id": payable_id, "debit": total, "credit": 0, "partner_id": original[1]},
                         {"account_id": inventory_id, "debit": 0, "credit": total, "partner_id": original[1]}])
        _audit(c, user_id, "POST_RETURN", "purchase_invoices", return_id,
               new_values={"number": number, "original_invoice_id": original_invoice_id, "product_id": product_id, "quantity": quantity, "total": total})
        return return_id


def create_payroll_draft(period_start: str, period_end: str, user_id: int | None) -> int:
    if period_end < period_start:
        raise ValueError("نهاية الفترة يجب أن تكون بعد بدايتها")
    with db.transaction() as c:
        number = _next_number(c, "PAYROLL")
        c.execute("INSERT INTO payroll_runs(number,period_start,period_end,status,created_by) VALUES(?,?,?,'DRAFT',?)",
                  (number, period_start, period_end, user_id))
        run_id = c.lastrowid
        employees = c.execute("SELECT id,base_salary FROM employees WHERE is_active=1 AND (termination_date IS NULL OR termination_date>=?)", (period_start,)).fetchall()
        for employee_id, base_salary in employees:
            c.execute("INSERT INTO payslips(run_id,employee_id,base_salary,allowances,deductions,advances_deducted,net_pay) VALUES(?,?,?,0,0,0,?)",
                      (run_id, employee_id, base_salary, base_salary))
        _audit(c, user_id, "CREATE_DRAFT", "payroll_runs", run_id,
               new_values={"number": number, "period_start": period_start, "period_end": period_end, "payslip_count": len(employees)})
        return run_id


def get_field_choices(field_name: str):
    mapping = {
        "section_id": ("SELECT id,name FROM sections WHERE is_active=1 ORDER BY name",),
        "unit_id": ("SELECT id,name FROM units WHERE is_active=1 ORDER BY name",),
        "tax_rate_id": ("SELECT id,name || ' (' || printf('%.2f%%',rate_bp/100.0) || ')' FROM tax_rates WHERE is_active=1 ORDER BY name",),
        "product_id": ("SELECT id,name FROM products WHERE is_active=1 ORDER BY name",),
        "warehouse_id": ("SELECT id,name FROM warehouses WHERE is_active=1 ORDER BY name",),
        "supplier_id": ("SELECT id,name FROM partners WHERE is_supplier=1 AND is_active=1 ORDER BY name",),
        "customer_id": ("SELECT id,name FROM partners WHERE is_customer=1 AND is_active=1 ORDER BY name",),
        "original_sale_id": ("SELECT id,number FROM sales WHERE sale_type='SALE' AND status='POSTED' ORDER BY id DESC",),
        "original_invoice_id": ("SELECT id,number FROM purchase_invoices WHERE invoice_type='PURCHASE' AND status='POSTED' ORDER BY id DESC",),
        "partner_id": ("SELECT id,name FROM partners WHERE is_active=1 ORDER BY name",),
        "method_id": ("SELECT id,name FROM payment_methods WHERE is_active=1 ORDER BY name",),
        "account_id": ("SELECT id,code || ' - ' || name FROM accounts WHERE is_active=1 ORDER BY code",),
        "department_id": ("SELECT id,name FROM departments WHERE is_active=1 ORDER BY name",),
        "employee_id": ("SELECT id,full_name FROM employees WHERE is_active=1 ORDER BY full_name",),
        "role_id": ("SELECT id,name FROM roles ORDER BY name",),
        "user_id": ("SELECT id,username FROM users WHERE is_active=1 ORDER BY username",),
        "shift_id": ("SELECT cash_shifts.id,'#' || cash_shifts.id || ' - ' || users.username FROM cash_shifts JOIN users ON users.id=cash_shifts.user_id WHERE cash_shifts.status='OPEN' ORDER BY cash_shifts.id DESC",),
    }
    if field_name not in mapping:
        return []
    return _fetch_all(mapping[field_name][0])


def get_role_permissions(role_id: int):
    all_permissions = _fetch_all("SELECT id,code,COALESCE(description,'') FROM permissions ORDER BY code")
    assigned = {row[0] for row in _fetch_all("SELECT permission_id FROM role_permissions WHERE role_id=?", (role_id,))}
    role = _fetch_one("SELECT name,is_system FROM roles WHERE id=?", (role_id,))
    return all_permissions, assigned, role


def set_role_permissions(role_id: int, permission_ids: list[int], user_id: int | None = None):
    with db.transaction() as c:
        role = c.execute("SELECT id,name FROM roles WHERE id=?", (role_id,)).fetchone()
        if not role:
            raise ValueError("الدور غير موجود")
        if role[1] == "Admin":
            all_ids = {r[0] for r in c.execute("SELECT id FROM permissions").fetchall()}
            if set(int(x) for x in permission_ids) != all_ids:
                raise ValueError("يجب أن يحتفظ دور Admin بجميع الصلاحيات لتجنب قفل الإدارة")
        c.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        for permission_id in sorted(set(int(x) for x in permission_ids)):
            c.execute("INSERT INTO role_permissions(role_id,permission_id) VALUES(?,?)", (role_id, permission_id))
        _audit(c, user_id, "UPDATE_PERMISSIONS", "roles", int(role_id), new_values={"permission_ids": sorted(set(int(x) for x in permission_ids))})

