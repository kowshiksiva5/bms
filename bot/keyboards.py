#!/usr/bin/env python3
from __future__ import annotations
from typing import List, Dict, Set
from datetime import datetime, timedelta

def kb_main(mid: str, state: str)->Dict:
    running=(state=="RUNNING")
    return {"inline_keyboard":[
        [{"text":"Status","callback_data":f"status|{mid}"},
         {"text":("Pause" if running else "Resume"),"callback_data":f"{'pause' if running else 'resume'}|{mid}"},
         {"text":"Stop","callback_data":f"stop|{mid}"}],
        [{"text":"Snooze 2h","callback_data":f"snooze|{mid}|2h"},
         {"text":"Snooze 6h","callback_data":f"snooze|{mid}|6h"},
         {"text":"Clear snooze","callback_data":f"snooze|{mid}|clear"}],
        [{"text":"Edit dates","callback_data":f"edit_dates|{mid}"},
         {"text":"Edit theatres","callback_data":f"edit_theatres|{mid}"},
         {"text":"Restart driver","callback_data":f"restart|{mid}"}],
        [{"text":"Discover","callback_data":f"discover|{mid}"},
         {"text":"Delete","callback_data":f"delete|{mid}"}],
    ]}

def _fmt(d: datetime)->str: return d.strftime("%Y-%m-%d")
def _d8(d: datetime)->str:  return d.strftime("%Y%m%d")

def kb_date_picker(id_: str, selected: Set[str], page:int=0, total_days:int=28, prefix:str="d")->Dict:
    days_per_page=7
    start=datetime.now().date()+timedelta(days=page*days_per_page)
    rows=[]
    for i in range(days_per_page):
        dt=datetime.combine(start+timedelta(days=i), datetime.min.time())
        d8=_d8(dt); label=_fmt(dt); mark="✅" if d8 in selected else "☐"
        rows.append([{"text":f"{mark} {label}","callback_data":f"{prefix}pick|{id_}|{d8}"}])
    nav=[]
    if page>0: nav.append({"text":"◀ Prev","callback_data":f"{prefix}pg|{id_}|{page-1}"})
    if (page+1)*days_per_page<total_days: nav.append({"text":"Next ▶","callback_data":f"{prefix}pg|{id_}|{page+1}"})
    ctr=[[{"text":"Save","callback_data":f"{prefix}save|{id_}"},
          {"text":"Cancel","callback_data":f"{prefix}cancel|{id_}"}]]
    if nav: return {"inline_keyboard":rows+[nav]+ctr}
    return {"inline_keyboard":rows+ctr}

def kb_theatre_picker(id_: str, items: List[str], selected: Set[str], page:int=0, page_size:int=8, prefix:str="t")->Dict:
    if not items:
        return {"inline_keyboard":[
            [{"text":"No theatres available","callback_data":f"{prefix}noop|{id_}"}],
            [{"text":"Back","callback_data":f"{prefix}cancel|{id_}"}]
        ]}
    start=page*page_size; chunk=items[start:start+page_size]
    rows=[]
    for i,name in enumerate(chunk):
        mark="✅" if name in selected else "☐"
        rows.append([{"text":f"{mark} {name[:56]}","callback_data":f"{prefix}pick|{id_}|{start+i}"}])
    nav=[]
    if page>0: nav.append({"text":"◀ Prev","callback_data":f"{prefix}pg|{id_}|{page-1}"})
    if start+page_size<len(items): nav.append({"text":"Next ▶","callback_data":f"{prefix}pg|{id_}|{page+1}"})
    ctr=[[{"text":"Save","callback_data":f"{prefix}save|{id_}"},
          {"text":"Cancel","callback_data":f"{prefix}cancel|{id_}"}]]
    kb=rows
    if nav: kb+=[nav]
    return {"inline_keyboard":kb+ctr}

def kb_interval_picker(sid: str, current:int=5)->Dict:
    choices=[2,5,10,15,30]
    row=[{"text":("• "+str(m)+"m" if m==current else str(m)+"m"),
          "callback_data":f"ivalset|{sid}|{m}"} for m in choices]
    row2=[
        {"text":"Back","callback_data":f"ivalback|{sid}"},
        {"text":"Next: Duration →","callback_data":f"idurnext|{sid}"},
    ]
    return {"inline_keyboard":[row,row2]}

def kb_duration_picker(sid: str, mode:str, rolling:int=7, end_d8:str|None=None)->Dict:
    row1=[
        {"text":"Fixed" + (" •" if mode=="FIXED" else ""), "callback_data":f"dur|{sid}|FIXED"},
    ]
    row2=[
        {"text":"−","callback_data":f"rminus|{sid}"},
        {"text":f"Rolling {rolling}d" + (" •" if mode=='ROLLING' else ""), "callback_data":f"dur|{sid}|ROLLING"},
        {"text":"+","callback_data":f"rplus|{sid}"},
    ]
    if end_d8:
        end_fmt=f"{end_d8[:4]}-{end_d8[4:6]}-{end_d8[6:]}"
    else:
        end_fmt="(pick)"
    row3=[
        {"text":f"Until {end_fmt}" + (" •" if mode=='UNTIL' else ""), "callback_data":f"uopen|{sid}|0"},
    ]
    row4=[
        {"text":"Back","callback_data":f"idurback|{sid}"},
        {"text":"Next: Heartbeat →","callback_data":f"idur2hb|{sid}"},
    ]
    return {"inline_keyboard":[row1,row2,row3,row4]}

def kb_heartbeat_picker(sid: str, current:int=180)->Dict:
    choices=[30,60,120,180,360]
    row=[{"text":("• "+str(m)+"m" if m==current else str(m)+"m"),
          "callback_data":f"hbset|{sid}|{m}"} for m in choices]
    row2=[
        {"text":"Back","callback_data":f"hbback|{sid}"},
        {"text":"Finish: Create & Start","callback_data":f"cfinish|{sid}|start"},
        {"text":"Finish: Create Paused","callback_data":f"cfinish|{sid}|pause"},
    ]
    return {"inline_keyboard":[row,row2]}
