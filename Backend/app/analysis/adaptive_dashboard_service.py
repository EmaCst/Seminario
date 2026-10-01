from sqlalchemy import text

from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.connection import get_connection
from app.database.database_manager import database_manager

DOMAIN_KPI_ROLES={"retail":["products","customers","sales","payments"],"education":["students","teachers","courses","enrollments"],"healthcare":["patients","doctors","appointments","admissions"],"transportation":["vehicles","drivers","routes","trips"],"hospitality":["rooms","guests","reservations","stays"],"restaurant":["menu_items","tables","orders","ingredients"],"professional_services":["clients","services","projects","invoices"],"finance_accounting":["accounts","transactions","journal_entries"],"manufacturing":["products","materials","machines","production_orders"],"human_resources":["employees","departments","attendance","payroll"]}
DOMAIN_TREND_PRIORITY={"retail":["sales","payments","orders"],"education":["enrollments","attendance","grades"],"healthcare":["appointments","admissions","treatments"],"transportation":["trips","tickets"],"hospitality":["reservations","stays"],"restaurant":["orders"],"professional_services":["appointments","projects","invoices","payments"],"finance_accounting":["transactions","journal_entries"],"manufacturing":["production_orders"],"human_resources":["attendance","payroll"]}
DOMAIN_STATUS_PRIORITY={"retail":["payments","sales","orders"],"education":["enrollments","attendance","students"],"healthcare":["appointments","admissions","treatments"],"transportation":["trips","vehicles","drivers","tickets"],"hospitality":["reservations","rooms","stays"],"restaurant":["orders","tables"],"professional_services":["projects","appointments","invoices"],"finance_accounting":["transactions"],"manufacturing":["production_orders","machines"],"human_resources":["employees","attendance"]}

def _provider(): return database_manager.status().get("provider") or "sqlserver"
def _quote(identifier):
    if _provider() in ("postgresql","excel"): return '"'+identifier.replace('"','""')+'"'
    return "["+identifier.replace("]","]]" )+"]"

def _count_table(table):
    with get_connection() as c: row=c.execute(text(f"SELECT COUNT(*) AS total FROM {_quote(table)};")).mappings().first()
    return int(row["total"] if row else 0)

def _monthly_count(table,date_column):
    qtable,qdate=_quote(table),_quote(date_column); provider=_provider()
    if provider=="postgresql":
        sql=text(f"SELECT EXTRACT(YEAR FROM {qdate})::int AS year, EXTRACT(MONTH FROM {qdate})::int AS month, COUNT(*) AS total FROM {qtable} WHERE {qdate} IS NOT NULL GROUP BY EXTRACT(YEAR FROM {qdate}),EXTRACT(MONTH FROM {qdate}) ORDER BY EXTRACT(YEAR FROM {qdate}),EXTRACT(MONTH FROM {qdate});")
    elif provider=="excel":
        sql=text(f"SELECT CAST(strftime('%Y',{qdate}) AS INTEGER) AS year, CAST(strftime('%m',{qdate}) AS INTEGER) AS month, COUNT(*) AS total FROM {qtable} WHERE {qdate} IS NOT NULL GROUP BY strftime('%Y',{qdate}),strftime('%m',{qdate}) ORDER BY strftime('%Y',{qdate}),strftime('%m',{qdate});")
    else:
        sql=text(f"SELECT YEAR({qdate}) AS year, MONTH({qdate}) AS month, COUNT(*) AS total FROM {qtable} WHERE {qdate} IS NOT NULL GROUP BY YEAR({qdate}),MONTH({qdate}) ORDER BY YEAR({qdate}),MONTH({qdate});")
    with get_connection() as c: rows=c.execute(sql).mappings().all()
    return [{"year":int(r["year"]),"month":int(r["month"]),"total":int(r["total"])} for r in rows if r["year"] is not None and r["month"] is not None]

def _status_distribution(table,status_column):
    qtable,qstatus=_quote(table),_quote(status_column); provider=_provider()
    if provider in ("postgresql","excel"):
        sql=text(f"SELECT CAST({qstatus} AS VARCHAR(255)) AS label,COUNT(*) AS total FROM {qtable} WHERE {qstatus} IS NOT NULL GROUP BY CAST({qstatus} AS VARCHAR(255)) ORDER BY total DESC LIMIT 12;")
    else:
        sql=text(f"SELECT TOP 12 CAST({qstatus} AS NVARCHAR(255)) AS label,COUNT(*) AS total FROM {qtable} WHERE {qstatus} IS NOT NULL GROUP BY CAST({qstatus} AS NVARCHAR(255)) ORDER BY total DESC;")
    with get_connection() as c: rows=c.execute(sql).mappings().all()
    return [{"label":str(r["label"]),"total":int(r["total"])} for r in rows]

def _entity_counts(entities):
    counts={}
    for role,entity in entities.items():
        table=entity.get("table")
        if not table: continue
        try: counts[role]=_count_table(table)
        except Exception: counts[role]=0
    return counts

def _select_kpis(domain,entities,counts):
    selected=[]
    for role in DOMAIN_KPI_ROLES.get(domain,[]):
        if role in entities and role not in selected: selected.append(role)
    # Avoid duplicate KPI cards when a denormalized Excel sheet maps to several semantic roles.
    used_tables=set()
    unique=[]
    for role in selected+list(entities):
        if role not in entities: continue
        table=entities[role].get("table")
        if not table or table in used_tables: continue
        used_tables.add(table); unique.append(role)
        if len(unique)>=4: break
    return [{"role":r,"value":counts.get(r,0),"table":entities[r].get("table")} for r in unique]

def _select_trend(domain,entities):
    seen=set()
    for role in DOMAIN_TREND_PRIORITY.get(domain,[])+list(entities):
        if role in seen: continue
        seen.add(role); entity=entities.get(role)
        if not entity: continue
        table=entity.get("table"); date=(entity.get("columns") or {}).get("date")
        if not table or not date: continue
        try:
            data=_monthly_count(table,date)
            if data: return {"available":True,"role":role,"data":data}
        except Exception: continue
    return {"available":False,"role":None,"data":[]}

def _select_status(domain,entities):
    seen=set()
    for role in DOMAIN_STATUS_PRIORITY.get(domain,[])+list(entities):
        if role in seen: continue
        seen.add(role); entity=entities.get(role)
        if not entity: continue
        table=entity.get("table"); status=(entity.get("columns") or {}).get("status")
        if not table or not status: continue
        try:
            data=_status_distribution(table,status)
            if data: return {"available":True,"role":role,"data":data}
        except Exception: continue
    return {"available":False,"role":None,"data":[]}

def get_adaptive_dashboard_summary():
    analysis=inspect_semantic_model(); semantic=analysis.get("semantic_model") or {}; domain=semantic.get("domain"); entities=semantic.get("entities") or {}; counts=_entity_counts(entities)
    return {"database":analysis.get("database"),"provider":_provider(),"domain":domain,"domain_confidence":semantic.get("domain_confidence"),"ambiguous_domain":semantic.get("ambiguous_domain",False),"kpis":_select_kpis(domain,entities,counts),"trend":_select_trend(domain,entities),"status_distribution":_select_status(domain,entities),"entity_counts":[{"role":r,"value":counts.get(r,0),"table":e.get("table"),"confidence":e.get("confidence")} for r,e in entities.items()],"relations_detected":len(semantic.get("relations") or []),"unmapped_tables":semantic.get("unmapped_tables") or []}
