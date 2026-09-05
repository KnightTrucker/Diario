#!/usr/bin/env python3
import argparse, io, json, os, re, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    from pypdf import PdfReader
except Exception:
    requests = BeautifulSoup = PdfReader = None

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "hgv_europe.json"
UA = "KnightTrucker-HGV-Updater/1.0 (+https://github.com/KnightTrucker/Diario)"
MONTH_IT = {"GENNAIO":1,"FEBBRAIO":2,"MARZO":3,"APRILE":4,"MAGGIO":5,"GIUGNO":6,"LUGLIO":7,"AGOSTO":8,"SETTEMBRE":9,"OTTOBRE":10,"NOVEMBRE":11,"DICEMBRE":12}
MONTH_FR = {"janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12}


def easter_sunday(year:int)->date:
    # Meeus/Jones/Butcher Gregorian algorithm
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31; day=((h+l-7*m+114)%31)+1
    return date(year,month,day)


def iso_dt(d:date, hhmm:str)->str:
    return f"{d.isoformat()}T{hhmm}:00"


def next_day_dt(d:date, hhmm:str)->str:
    return iso_dt(d+timedelta(days=1),hhmm)


def daterange(start:date,end:date):
    d=start
    while d<=end:
        yield d
        d+=timedelta(days=1)


def add_event(events, country, year, kind, title, start_at, end_at, scope, threshold, notes, source, slug):
    events.append({
        "id": f"AUTO-{country}-{year}-{slug}", "country": country, "kind": kind,
        "title": title, "start_at": start_at, "end_at": end_at, "scope": scope,
        "threshold": threshold, "notes": notes, "source": source
    })


def holiday_definitions(year:int):
    e=easter_sunday(year)
    data={
      "IT":[(date(year,1,1),"Capodanno","national","IT_MIT"),(date(year,1,6),"Epifania","national","IT_MIT"),(e,"Pasqua","national","IT_MIT"),(e+timedelta(days=1),"Lunedì dell’Angelo","national","IT_MIT"),(date(year,4,25),"Festa della Liberazione","national","IT_MIT"),(date(year,5,1),"Festa dei Lavoratori","national","IT_MIT"),(date(year,6,2),"Festa della Repubblica","national","IT_MIT"),(date(year,8,15),"Ferragosto / Assunzione","national","IT_MIT"),(date(year,11,1),"Ognissanti","national","IT_MIT"),(date(year,12,8),"Immacolata Concezione","national","IT_MIT"),(date(year,12,25),"Natale","national","IT_MIT"),(date(year,12,26),"Santo Stefano","national","IT_MIT")],
      "FR":[(date(year,1,1),"Jour de l’An","national","FR_GENERAL"),(e+timedelta(days=1),"Lundi de Pâques","national","FR_GENERAL"),(date(year,5,1),"Fête du Travail","national","FR_GENERAL"),(date(year,5,8),"Victoire 1945","national","FR_GENERAL"),(e+timedelta(days=39),"Ascension","national","FR_GENERAL"),(e+timedelta(days=50),"Lundi de Pentecôte","national","FR_GENERAL"),(date(year,7,14),"Fête nationale","national","FR_GENERAL"),(date(year,8,15),"Assomption","national","FR_GENERAL"),(date(year,11,1),"Toussaint","national","FR_GENERAL"),(date(year,11,11),"Armistice","national","FR_GENERAL"),(date(year,12,25),"Noël","national","FR_GENERAL")],
      "AT":[(date(year,1,1),"Neujahr","national","AT_STVO"),(date(year,1,6),"Heilige Drei Könige","national","AT_STVO"),(e+timedelta(days=1),"Ostermontag","national","AT_STVO"),(date(year,5,1),"Staatsfeiertag","national","AT_STVO"),(e+timedelta(days=39),"Christi Himmelfahrt","national","AT_STVO"),(e+timedelta(days=50),"Pfingstmontag","national","AT_STVO"),(e+timedelta(days=60),"Fronleichnam","national","AT_STVO"),(date(year,8,15),"Mariä Himmelfahrt","national","AT_STVO"),(date(year,10,26),"Nationalfeiertag","national","AT_STVO"),(date(year,11,1),"Allerheiligen","national","AT_STVO"),(date(year,12,8),"Mariä Empfängnis","national","AT_STVO"),(date(year,12,25),"Christtag","national","AT_STVO"),(date(year,12,26),"Stefanitag","national","AT_STVO")],
      "DE":[(date(year,1,1),"Neujahr","national","DE_STVO"),(e-timedelta(days=2),"Karfreitag","national","DE_STVO"),(e+timedelta(days=1),"Ostermontag","national","DE_STVO"),(date(year,5,1),"Tag der Arbeit","national","DE_STVO"),(e+timedelta(days=39),"Christi Himmelfahrt","national","DE_STVO"),(e+timedelta(days=50),"Pfingstmontag","national","DE_STVO"),(e+timedelta(days=60),"Fronleichnam","regional: BW,BY,HE,NW,RP,SL","DE_STVO"),(date(year,10,3),"Tag der Deutschen Einheit","national","DE_STVO"),(date(year,10,31),"Reformationstag","regional: BB,HB,HH,MV,NI,SN,ST,SH,TH","DE_STVO"),(date(year,11,1),"Allerheiligen","regional: BW,BY,NW,RP,SL","DE_STVO"),(date(year,12,25),"1. Weihnachtstag","national","DE_STVO"),(date(year,12,26),"2. Weihnachtstag","national","DE_STVO")],
      "CH":[(date(year,1,1),"Capodanno","hgv","CH_HOL"),(e-timedelta(days=2),"Venerdì Santo","hgv","CH_HOL"),(e+timedelta(days=1),"Lunedì di Pasqua","hgv","CH_HOL"),(e+timedelta(days=39),"Ascensione","hgv","CH_HOL"),(e+timedelta(days=50),"Lunedì di Pentecoste","hgv","CH_HOL"),(date(year,8,1),"Festa nazionale svizzera","hgv","CH_HOL"),(date(year,12,25),"Natale","hgv","CH_HOL"),(date(year,12,26),"Santo Stefano","hgv/condizionale","CH_HOL")],
      "BE":[(date(year,1,1),"Capodanno","national","BE_HOL"),(e+timedelta(days=1),"Lunedì di Pasqua","national","BE_HOL"),(date(year,5,1),"Festa del Lavoro","national","BE_HOL"),(e+timedelta(days=39),"Ascensione","national","BE_HOL"),(e+timedelta(days=50),"Lunedì di Pentecoste","national","BE_HOL"),(date(year,7,21),"Festa nazionale","national","BE_HOL"),(date(year,8,15),"Assunzione","national","BE_HOL"),(date(year,11,1),"Ognissanti","national","BE_HOL"),(date(year,11,11),"Armistizio","national","BE_HOL"),(date(year,12,25),"Natale","national","BE_HOL")],
      "LU":[(date(year,1,1),"Capodanno","national","LU_TRANS"),(e+timedelta(days=1),"Lunedì di Pasqua","national","LU_TRANS"),(date(year,5,1),"Festa del Lavoro","national","LU_TRANS"),(date(year,5,9),"Giornata dell’Europa","national","LU_TRANS"),(e+timedelta(days=39),"Ascensione","national","LU_TRANS"),(e+timedelta(days=50),"Lunedì di Pentecoste","national","LU_TRANS"),(date(year,6,23),"Festa nazionale","national","LU_TRANS"),(date(year,8,15),"Assunzione","national","LU_TRANS"),(date(year,11,1),"Ognissanti","national","LU_TRANS"),(date(year,12,25),"Natale","national","LU_TRANS"),(date(year,12,26),"Santo Stefano","national","LU_TRANS")],
      "ES":[(date(year,1,1),"Año Nuevo","national/common","ES_DGT"),(date(year,1,6),"Epifanía del Señor","national/common","ES_DGT"),(e-timedelta(days=2),"Viernes Santo","national/common","ES_DGT"),(date(year,5,1),"Fiesta del Trabajo","national/common","ES_DGT"),(date(year,8,15),"Asunción de la Virgen","national/common","ES_DGT"),(date(year,10,12),"Fiesta Nacional de España","national/common","ES_DGT"),(date(year,11,1),"Todos los Santos","national/common","ES_DGT"),(date(year,12,6),"Día de la Constitución","national/common","ES_DGT"),(date(year,12,8),"Inmaculada Concepción","national/common","ES_DGT"),(date(year,12,25),"Navidad","national/common","ES_DGT")],
      "NL":[]
    }
    king=date(year,4,27)
    if king.weekday()==6: king=date(year,4,26)
    data["NL"]=[(date(year,1,1),"Nieuwjaarsdag","national","NL_HOL"),(e-timedelta(days=2),"Goede vrijdag","official","NL_HOL"),(e,"Eerste paasdag","official","NL_HOL"),(e+timedelta(days=1),"Tweede paasdag","official","NL_HOL"),(king,"Koningsdag","official","NL_HOL"),(date(year,5,5),"Bevrijdingsdag","official","NL_HOL"),(e+timedelta(days=39),"Hemelvaartsdag","official","NL_HOL"),(e+timedelta(days=49),"Eerste pinksterdag","official","NL_HOL"),(e+timedelta(days=50),"Tweede pinksterdag","official","NL_HOL"),(date(year,12,25),"Eerste kerstdag","official","NL_HOL"),(date(year,12,26),"Tweede kerstdag","official","NL_HOL")]
    return data


def merge_holidays(db, years):
    all_by_cc={cc:[] for cc in db.get("countries",{})}
    existing=db.get("holidays",{})
    keep_years=set(range(min(years)-5,min(years))) | set(years)
    # retain historical entries, but regenerate target years deterministically
    for cc, arr in existing.items():
        for h in arr:
            try: y=int(h["date"][:4])
            except Exception: continue
            if y not in years: all_by_cc.setdefault(cc,[]).append(h)
    for y in years:
        defs=holiday_definitions(y)
        for cc,items in defs.items():
            for d,name,scope,source in items:
                all_by_cc.setdefault(cc,[]).append({"date":d.isoformat(),"name":name,"scope":scope,"source":source})
    for cc in all_by_cc:
        uniq={ (h.get("date"),h.get("name"),h.get("scope")):h for h in all_by_cc[cc] }
        all_by_cc[cc]=sorted(uniq.values(),key=lambda x:(x.get("date",""),x.get("name","")))
    db["holidays"]=all_by_cc


def generate_recurring(year:int, holidays):
    ev=[]
    # France: general weekend and permanent Île-de-France rules
    for d in daterange(date(year,1,1),date(year,12,31)):
        wd=d.weekday()
        if wd==5:
            add_event(ev,"FR",year,"ban","Divieto generale weekend",iso_dt(d,"22:00"),next_day_dt(d,"22:00"),"Tutta la rete stradale metropolitana","> 7,5 t","Trasporto merci; salve le deroghe previste dall’arrêté del 16 aprile 2021.","FR_GENERAL",f"WK-{d:%m%d}")
            add_event(ev,"FR",year,"regional","Île-de-France – uscita da Parigi",iso_dt(d,"10:00"),iso_dt(d,"18:00"),"Tratti autostradali dell’area parigina indicati dall’art. 3, senso Parigi → provincia","> 7,5 t","Regola permanente del sabato.","FR_GENERAL",f"IDF-SA-{d:%m%d}")
        elif wd==4:
            add_event(ev,"FR",year,"regional","Île-de-France – uscita da Parigi",iso_dt(d,"16:00"),iso_dt(d,"21:00"),"Tratti autostradali dell’area parigina indicati dall’art. 3, senso Parigi → provincia","> 7,5 t","Regola permanente del venerdì.","FR_GENERAL",f"IDF-FR-{d:%m%d}")
        elif wd==6:
            add_event(ev,"FR",year,"regional","Île-de-France – domenica sera",iso_dt(d,"22:00"),next_day_dt(d,"00:00"),"Tratti autostradali indicati dall’art. 3, entrambi i sensi secondo la disciplina","> 7,5 t","Si aggiunge al regime generale.","FR_GENERAL",f"IDF-SU-{d:%m%d}")
        elif wd==0:
            add_event(ev,"FR",year,"regional","Île-de-France – rientro verso Parigi",iso_dt(d,"06:00"),iso_dt(d,"10:00"),"Tratti autostradali indicati dall’art. 3, senso provincia → Parigi","> 7,5 t","Regola permanente del lunedì.","FR_GENERAL",f"IDF-MO-{d:%m%d}")
    for h in holidays["FR"]:
        d=date.fromisoformat(h["date"]); eve=d-timedelta(days=1)
        add_event(ev,"FR",year,"holiday",f"Festivo – {h['name']}",iso_dt(eve,"22:00"),iso_dt(d,"22:00"),"Tutta la rete stradale metropolitana","> 7,5 t","Divieto dalla vigilia alle 22:00 del giorno festivo; può sovrapporsi al divieto weekend.","FR_GENERAL",f"HOL-{d:%m%d}")

    # Germany
    for d in daterange(date(year,1,1),date(year,12,31)):
        if d.weekday()==6:
            add_event(ev,"DE",year,"ban","Divieto domenicale",iso_dt(d,"00:00"),iso_dt(d,"22:00"),"Intera rete stradale tedesca","Autocarri > 7,5 t e autocarri con rimorchio","Trasporto commerciale/oneroso di merci; eccezioni previste dalla StVO.","DE_STVO",f"SUN-{d:%m%d}")
        if d.weekday()==5 and date(year,7,1)<=d<=date(year,8,31):
            add_event(ev,"DE",year,"seasonal","Divieto sabato estivo",iso_dt(d,"07:00"),iso_dt(d,"20:00"),"Tratte autostradali e federali indicate dalla Ferienreiseverordnung","Autocarri > 7,5 t e autocarri con rimorchio","Divieto estivo ricorrente 1 luglio–31 agosto sulle tratte specifiche della Ferienreiseverordnung.","DE_FER",f"SUM-{d:%m%d}")
    for h in holidays["DE"]:
        d=date.fromisoformat(h["date"])
        add_event(ev,"DE",year,"holiday",f"Festivo – {h['name']}",iso_dt(d,"00:00"),iso_dt(d,"22:00"),"Intera rete nazionale" if h["scope"]=="national" else h["scope"],"Autocarri > 7,5 t e autocarri con rimorchio","Festività rilevante ai fini del §30 StVO; verificare l’ambito regionale indicato.","DE_STVO",f"HOL-{d:%m%d}-{re.sub('[^A-Z0-9]','',h['name'].upper())[:8]}")

    # Austria
    for d in daterange(date(year,1,1),date(year,12,31)):
        add_event(ev,"AT",year,"night","Divieto notturno",iso_dt(d,"22:00"),next_day_dt(d,"05:00"),"Intera rete stradale, salvo eccezioni/deroghe","> 7,5 t","Sono esclusi, tra gli altri, i veicoli riconosciuti 'lärmarme' nelle condizioni previste dalla legge.","AT_STVO",f"N-{d:%m%d}")
        if d.weekday()==5:
            add_event(ev,"AT",year,"ban","Divieto del sabato",iso_dt(d,"15:00"),next_day_dt(d,"00:00"),"Intera rete stradale","> 7,5 t; oppure autocarro+rimorchio se motrice o rimorchio >3,5 t","Regola generale §42 StVO.","AT_STVO",f"SAT-{d:%m%d}")
        if d.weekday()==6:
            add_event(ev,"AT",year,"ban","Divieto domenicale",iso_dt(d,"00:00"),iso_dt(d,"22:00"),"Intera rete stradale","> 7,5 t; oppure autocarro+rimorchio se motrice o rimorchio >3,5 t","Regola generale §42 StVO.","AT_STVO",f"SUN-{d:%m%d}")
    for h in holidays["AT"]:
        d=date.fromisoformat(h["date"])
        add_event(ev,"AT",year,"holiday",f"Festivo – {h['name']}",iso_dt(d,"00:00"),iso_dt(d,"22:00"),"Intera rete stradale","> 7,5 t; oppure autocarro+rimorchio se motrice o rimorchio >3,5 t","Festività legale nazionale; possibili eccezioni previste dalla StVO.","AT_STVO",f"HOL-{d:%m%d}")

    # Switzerland
    for d in daterange(date(year,1,1),date(year,12,31)):
        add_event(ev,"CH",year,"night","Divieto notturno",iso_dt(d,"22:00"),next_day_dt(d,"05:00"),"Intera rete stradale svizzera",">3,5 t; autoarticolati >5 t; rimorchi >3,5 t","Autorizzazioni speciali per viaggi inevitabili.","CH_ASTRA",f"N-{d:%m%d}")
        if d.weekday()==6:
            add_event(ev,"CH",year,"ban","Divieto domenicale",iso_dt(d,"00:00"),next_day_dt(d,"00:00"),"Intera rete; salvo Cantoni/parti di Cantone dove ricorrenze specifiche non valgono",">3,5 t; autoarticolati >5 t; rimorchi >3,5 t","Divieto generale domenicale.","CH_ASTRA",f"SUN-{d:%m%d}")
    for h in holidays["CH"]:
        d=date.fromisoformat(h["date"])
        add_event(ev,"CH",year,"holiday",f"Festivo con divieto – {h['name']}",iso_dt(d,"00:00"),next_day_dt(d,"00:00"),"Cantoni/parti di Cantone in cui la festività è osservata",">3,5 t; autoarticolati >5 t; rimorchi >3,5 t","Lista ufficiale USTRA delle festività assimilate alla domenica.","CH_HOL",f"HOL-{d:%m%d}")

    # Luxembourg weekend, plus destination-country holidays
    for d in daterange(date(year,1,1),date(year,12,31)):
        if d.weekday()==5:
            add_event(ev,"LU",year,"ban","Transito verso Francia – weekend",iso_dt(d,"21:30"),next_day_dt(d,"21:45"),"Rete stradale del Lussemburgo; transito Belgio/Germania → Francia","> 7,5 t","Trasporto interno e transito verso Belgio non ricadono in questo divieto direzionale.","LU_BISON",f"FR-WK-{d:%m%d}")
            add_event(ev,"LU",year,"ban","Transito verso Germania – weekend",iso_dt(d,"23:30"),next_day_dt(d,"21:45"),"Rete stradale del Lussemburgo; transito Belgio/Francia → Germania","> 7,5 t","Trasporto interno e transito verso Belgio non ricadono in questo divieto direzionale.","LU_BISON",f"DE-WK-{d:%m%d}")
    for h in holidays["FR"]:
        d=date.fromisoformat(h["date"]); eve=d-timedelta(days=1)
        add_event(ev,"LU",year,"holiday",f"Transito verso Francia – {h['name']}",iso_dt(eve,"21:30"),iso_dt(d,"21:45"),"Rete stradale Lussemburgo; transito verso Francia","> 7,5 t","Finestra legata al calendario festivo applicabile alla destinazione Francia.","LU_BISON",f"FR-HOL-{d:%m%d}")
    # German holidays relevant at Luxembourg border: national + RP/SL holidays, excluding Reformation
    for h in holidays["DE"]:
        if "Reformationstag" in h["name"]: continue
        if h["scope"].startswith("regional") and not any(x in h["scope"] for x in ("RP","SL")): continue
        d=date.fromisoformat(h["date"]); eve=d-timedelta(days=1)
        add_event(ev,"LU",year,"holiday",f"Transito verso Germania – {h['name']}",iso_dt(eve,"23:30"),iso_dt(d,"21:45"),"Rete stradale Lussemburgo; transito verso Germania","> 7,5 t","Finestra legata al calendario festivo applicabile alla destinazione Germania.","LU_BISON",f"DE-HOL-{d:%m%d}-{re.sub('[^A-Z0-9]','',h['name'].upper())[:8]}")

    # Belgium / Netherlands information records
    add_event(ev,"BE",year,"info","Nessun divieto nazionale generale weekend/festivi",iso_dt(date(year,1,1),"00:00"),iso_dt(date(year+1,1,1),"00:00"),"Belgio","—","Restano possibili restrizioni locali, di sorpasso, ambientali o temporanee.","BE_BISON","INFO")
    add_event(ev,"NL",year,"info","Nessun divieto nazionale generale weekend/festivi",iso_dt(date(year,1,1),"00:00"),iso_dt(date(year+1,1,1),"00:00"),"Olanda","—","Restano possibili restrizioni locali, ZES/ZBE, ponti, lavori o divieti temporanei.","NL_IRU","INFO")
    return ev


def http_get(url, binary=False, timeout=30):
    if requests is None: raise RuntimeError("requests non disponibile")
    r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"it,en;q=0.8"},timeout=timeout,allow_redirects=True)
    r.raise_for_status()
    return r.content if binary else r.text


def bing_discover(query, allowed_domains):
    if requests is None: return []
    url="https://www.bing.com/search?format=rss&q="+quote_plus(query)
    try:
        xml=http_get(url)
        import xml.etree.ElementTree as ET
        root=ET.fromstring(xml)
        out=[]
        for item in root.findall(".//item"):
            link=(item.findtext("link") or "").strip(); title=(item.findtext("title") or "").strip()
            host=urlparse(link).netloc.lower()
            if any(host==d or host.endswith("."+d) for d in allowed_domains): out.append((link,title))
        return out
    except Exception:
        return []


def find_annual_source(country, year):
    specs={
      "IT": (f'site:mit.gov.it "calendario {year}" "mezzi pesanti" divieti', ["mit.gov.it"]),
      "FR": (f'site:legifrance.gouv.fr "interdictions complémentaires" circulation marchandises "{year}"', ["legifrance.gouv.fr"]),
      "AT": (f'site:ris.bka.gv.at Fahrverbotskalender {year} Lastkraftwagen', ["ris.bka.gv.at"]),
      "ES": (f'site:boe.es "medidas especiales de regulación de tráfico" "{year}"', ["boe.es"]),
    }
    if country=="IT":
        direct=f"https://www.mit.gov.it/comunicazione/news/mezzi-pesanti-calendario-{year}-dei-divieti-di-circolazione-stradale"
        try:
            text=http_get(direct)
            if str(year) in text and "7,5" in text: return direct
        except Exception: pass
    if country not in specs: return None
    q,domains=specs[country]
    for link,title in bing_discover(q,domains):
        try:
            text=http_get(link)
            low=(title+" "+text[:200000]).lower()
            if str(year) in low:
                if country=="IT" and "mezzi pesanti" not in low: continue
                if country=="FR" and "interdictions" not in low: continue
                if country=="AT" and "fahrverbot" not in low: continue
                if country=="ES" and "regulación de tráfico" not in low and "regulacion de trafico" not in low: continue
                return link
        except Exception: continue
    return None


def parse_italy_annual(url, year, db):
    html=http_get(url)
    soup=BeautifulSoup(html,"html.parser")
    pdfs=[]
    for a in soup.find_all("a",href=True):
        href=urljoin(url,a["href"])
        if ".pdf" in href.lower(): pdfs.append(href)
    if not pdfs: raise RuntimeError("PDF decreto non trovato")
    pdf_url=next((u for u in pdfs if str(year) in u),pdfs[0])
    raw=http_get(pdf_url,binary=True,timeout=60)
    reader=PdfReader(io.BytesIO(raw)); text="\n".join((p.extract_text() or "") for p in reader.pages)
    pos=text.lower().find("allegato a")
    if pos<0: raise RuntimeError("Allegato A non trovato")
    cal=text[pos:]
    # Stop at Allegato B if present
    p2=cal.lower().find("allegato b",20)
    if p2>0: cal=cal[:p2]
    events=[]; hol={h["date"]:h["name"] for h in db["holidays"]["IT"] if h["date"].startswith(str(year))}
    months=list(MONTH_IT.items())
    # split by month labels so rows without repeated month inherit the right month
    hits=list(re.finditer(r"\b("+"|".join(MONTH_IT.keys())+r")\b",cal,re.I))
    for i,m in enumerate(hits):
        mon=MONTH_IT[m.group(1).upper()]; segment=cal[m.end():(hits[i+1].start() if i+1<len(hits) else len(cal))]
        segment=re.sub(r"\s+"," ",segment)
        for row in re.finditer(r"\b(\d{1,2})\s+(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})",segment,re.I):
            day=int(row.group(1)); start=row.group(2); end=row.group(3)
            try:d=date(year,mon,day)
            except ValueError: continue
            title=f"Festivo – {hol[d.isoformat()]}" if d.isoformat() in hol else "Divieto mezzi pesanti"
            add_event(events,"IT",year,"holiday" if d.isoformat() in hol else "ban",title,iso_dt(d,start),iso_dt(d,end),"Strade extraurbane italiane","> 7,5 t",f"Calendario nazionale {year}. Sono previste deroghe ed eccezioni specifiche dal decreto.",f"IT_MIT_{year}",f"OFF-{d:%m%d}-{start.replace(':','')}")
    if len(events)<45: raise RuntimeError(f"solo {len(events)} righe calendario estratte")
    db["sources"][f"IT_MIT_{year}"]={"label":f"MIT – Calendario divieti {year}","url":url,"document_url":pdf_url}
    return events


def parse_fr_dates(fragment, year):
    norm=fragment.replace("1er","1")
    out=[]
    pat=r"\b(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)(?:\s+(\d{4}))?"
    for m in re.finditer(pat,norm,re.I):
        y=int(m.group(3) or year); mon=MONTH_FR[m.group(2).lower()];
        try: out.append(date(y,mon,int(m.group(1))))
        except ValueError: pass
    return out


def parse_france_annual(url, year, db):
    text=BeautifulSoup(http_get(url),"html.parser").get_text(" ",strip=True)
    low=text.lower(); events=[]
    # Extract short windows around winter/summer clauses; these formulations have been stable for years.
    for label,kind,scope in [("période hivernale","winter","Réseau Auvergne-Rhône-Alpes indicato nell’annexe"),("période estivale","summer","Intera rete stradale della Francia metropolitana")]:
        idx=low.find(label)
        if idx<0: continue
        frag=text[idx:idx+1800]
        tm=re.search(r"de\s+(\d{1,2})\s+heures?\s+à\s+(\d{1,2})\s+heures?",frag,re.I)
        if not tm: continue
        dates=parse_fr_dates(frag,year)
        for d in dates:
            if d.year!=year: continue
            add_event(events,"FR",year,"seasonal",f"Divieto stagionale {('invernale' if kind=='winter' else 'estivo')}",iso_dt(d,f"{int(tm.group(1)):02d}:00"),iso_dt(d,f"{int(tm.group(2)):02d}:00"),scope,"> 7,5 t",f"Divieto complementare annuale {year}; verificare l’allegato per tratte e deroghe.",f"FR_ANNUAL_{year}",f"{kind.upper()}-{d:%m%d}")
    if not events: raise RuntimeError("nessuna data stagionale estratta")
    db["sources"][f"FR_ANNUAL_{year}"]={"label":f"Légifrance – Divieti complementari {year}","url":url}
    return events


def replace_auto_year_country(events,country,year,new_events,prefixes=None):
    y=str(year)
    kept=[]
    for e in events:
        eid=e.get("id","")
        if e.get("country")==country and eid.startswith(f"AUTO-{country}-{year}-"):
            if prefixes is None or any(eid.startswith(f"AUTO-{country}-{year}-{p}") for p in prefixes):
                continue
        kept.append(e)
    kept.extend(new_events)
    return kept


def summarize_coverage(db, target_years, source_status):
    coverage={}
    years=sorted(set(int(h["date"][:4]) for arr in db.get("holidays",{}).values() for h in arr if re.match(r"\d{4}-",h.get("date",""))))
    for y in years:
        coverage[str(y)]={}
        for cc in db["countries"]:
            cnt=sum(1 for e in db["events"] if e.get("country")==cc and (e.get("start_at","").startswith(str(y)) or e.get("end_at","").startswith(str(y))) and e.get("kind")!="info")
            status="verified_base"; note="Regole strutturali/ricorrenti presenti nel database."
            if cc=="IT":
                annual=any(e.get("country")=="IT" and (e.get("source")==f"IT_MIT_{y}" or (y==2026 and e.get("source")=="IT_MIT")) and (e.get("start_at","").startswith(str(y)) or e.get("end_at","").startswith(str(y))) for e in db["events"])
                status="verified_annual" if annual else "pending_annual"
                note="Calendario MIT annuale acquisito." if annual else "In attesa/ricerca del decreto MIT annuale ufficiale."
            elif cc=="FR":
                annual=any(e.get("country")=="FR" and (e.get("source")==f"FR_ANNUAL_{y}" or (y==2026 and e.get("source")=="FR_2026")) for e in db["events"])
                status="verified_annual" if annual else "base_rules_pending_specials"
                note="Regole generali e calendario stagionale annuale presenti." if annual else "Regole generali disponibili; divieti stagionali annuali in monitoraggio."
            elif cc=="AT":
                annual=any(e.get("country")=="AT" and e.get("source") in ({"AT_CAL_2026","AT_A10_2026","AT_A10_SPRING","AT_TIROL"} if y==2026 else {f"AT_ANNUAL_{y}"}) for e in db["events"])
                status="verified_annual" if annual else "base_rules_pending_specials"
                note="Regole generali e calendari speciali annuali presenti." if annual else "Regole generali disponibili; calendari speciali annuali in monitoraggio."
            elif cc=="ES":
                annual=any(e.get("country")=="ES" and y==2026 and e.get("source") in {"ES_BOE","ES_CAT","ES_PV","ES_NAV"} for e in db["events"])
                status="verified_annual" if annual else "pending_annual"
                note="Calendari DGT + territori autonomi presenti." if annual else "Festività disponibili; calendario annuale DGT/Catalogna/Paesi Baschi/Navarra in monitoraggio."
            elif cc in ("BE","NL"):
                status="no_general_ban"; note="Festività presenti; nessun divieto nazionale generale weekend/festivi."
            coverage[str(y)][cc]={"status":status,"events":cnt,"note":note}
    return coverage

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--offline",action="store_true",help="Non interroga le fonti web; genera solo regole ricorrenti e festività")
    ap.add_argument("--year",type=int,default=None)
    args=ap.parse_args()
    if not DB_PATH.exists():
        raise SystemExit("hgv_europe.json mancante: ripristinare il file dal repository/backup")
    db=json.loads(DB_PATH.read_text(encoding="utf-8"))
    today=date.today(); current=args.year or today.year
    years=[current,current+1]
    merge_holidays(db,years)

    # Regenerate deterministic recurring rules for current/next year.
    # On first migration, the current year already contains the hand-verified v22 dataset: do not duplicate it.
    original_events=list(db.get("events",[]))
    prev_db_year=int(db.get("year") or current)
    events=[e for e in original_events if not any(re.match(rf"^AUTO-[A-Z]{{2}}-{yy}-", e.get("id","")) for yy in years)]
    for y in years:
        had_auto=any(re.match(rf"^AUTO-[A-Z]{{2}}-{y}-", e.get("id","")) for e in original_events)
        manual_count=sum(1 for e in original_events if not e.get("id","").startswith("AUTO-") and e.get("start_at","").startswith(str(y)))
        migrate_verified_current=(y==prev_db_year and not had_auto and manual_count>500)
        if migrate_verified_current:
            continue
        h={cc:[x for x in db["holidays"].get(cc,[]) if x["date"].startswith(str(y))] for cc in db["countries"]}
        events.extend(generate_recurring(y,h))
    db["events"]=events

    source_status={}
    # annual official source acquisition
    if not args.offline:
        for cc in ("IT","FR","AT","ES"):
            for y in years:
                key=f"{cc}-{y}"; source_status[key]={"checked_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"status":"not_found","url":None}
                try:
                    u=find_annual_source(cc,y)
                    if not u: continue
                    source_status[key].update({"status":"found","url":u})
                    if cc=="IT":
                        ne=parse_italy_annual(u,y,db); db["events"]=replace_auto_year_country(db["events"],"IT",y,ne); source_status[key]["status"]="parsed"
                    elif cc=="FR":
                        ne=parse_france_annual(u,y,db)
                        # only replace annual seasonal parser records, not base recurring
                        db["events"]=[e for e in db["events"] if not (e.get("country")=="FR" and e.get("source")==f"FR_ANNUAL_{y}")]+ne
                        source_status[key]["status"]="parsed"
                    else:
                        source_status[key]["status"]="found_monitoring"
                except Exception as ex:
                    source_status[key]["status"]="error"; source_status[key]["error"]=str(ex)[:240]
    else:
        for cc in ("IT","FR","AT","ES"):
            for y in years:
                source_status[f"{cc}-{y}"]={"checked_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"status":"offline_generation","url":None}

    # Deduplicate and sort
    uniq={}
    for e in db["events"]:
        uniq[e.get("id") or json.dumps(e,sort_keys=True,ensure_ascii=False)]=e
    db["events"]=sorted(uniq.values(),key=lambda e:(e.get("start_at",""),e.get("country",""),e.get("id","")))
    years_available=sorted(set(int(h["date"][:4]) for arr in db.get("holidays",{}).values() for h in arr if re.match(r"\d{4}-",h.get("date",""))))
    db["schema_version"]=3
    db["database_version"]=datetime.now(timezone.utc).strftime("%Y.%m.%d-%H%MZ")
    db["checked_at"]=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    db["verified_at"]=today.isoformat()
    db["year"]=current
    db["years_available"]=years_available
    db["coverage_through"]=f"{max(years_available)}-12-31" if years_available else None
    db["source_status"]=source_status
    db["coverage"]=summarize_coverage(db,years,source_status)
    db["update_policy"]={
      "automatic":True,
      "normal_schedule":"weekly",
      "october_to_january":"every 2 days plus weekly",
      "safety":"Existing verified annual events are preserved. New annual data are only added when an official source is found and a parser validates the result.",
      "countries":["IT","FR","AT","DE","CH","BE","LU","ES","NL"]
    }
    DB_PATH.write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"HGV DB updated: {len(db['events'])} events; years={years_available}; coverage={db['coverage_through']}")

if __name__=="__main__": main()
