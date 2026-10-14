"""Extract uploaded directory snapshots; never infer email addresses."""
import csv, hashlib, json, re, sys
from pathlib import Path
EMAIL=re.compile(r'[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
PHONE=re.compile(r'(?<![\d-])(?:\(?[2-9]\d{2}\)?[ ._–-]+)?[2-9]\d{2}[ .–-]\d{4}(?!\d)(?:\s*(?:ext\.?|x)\s*\d+)?',re.I)
MAP={'adlc':'Deer Lodge','gallatinmt':'Gallatin','ravallicounty':'Ravalli','stillwatercountymt':'Stillwater','sanders':'Sanders','tetoncountymt':'Teton','valleycountymt':'Valley','madisoncountymt':'Madison','lincolncountymt':'Lincoln','libertycountymt':'Liberty','lakemt':'Lake','hillcounty':'Hill','granitecountymt':'Granite','sgcountymt':'Sweet Grass','custercountymt':'Custer','cascadecountymt':'Cascade','carbonmt':'Carbon','silverbow':'Silver Bow','broadwatercountymt':'Broadwater','bighorncountymt':'Big Horn','yellowstonecountymt':'Yellowstone','treasurecountymt':'Treasure'}
def clean(s):
 return re.sub(r'\s+',' ',str(s or '').replace('O!ce','Office').replace('O!cer','Officer').replace('A!airs','Affairs').replace('Sta#','Staff').replace('Sta"','Staff').replace('Sta!','Staff')).strip()
def phones(s):
 out=[]
 for m in PHONE.finditer(s):
  v=clean(m.group()); digits=re.sub(r'\D','',v.split('ext')[0])
  if len(digits)==7:v='406-'+v
  if v not in out:out.append(v)
 return out
def split_person(text):
 if ',' in text:
  title,name=text.rsplit(',',1);return clean(name),clean(title),'person'
 return '',text,'department'
contacts={}; raw=[]; coverage=[]
def add(county,agency,department,name,title,email,phone,source,file,loc,kind='person',note=''):
 name,title,department=map(clean,[name,title,department]);email=email.strip()
 if not name and not title: return
 if name.lower()=='vacant':kind='vacancy'
 key='|'.join(['MT',county,agency,department,name,title,email,phone]).lower()
 cid=hashlib.sha256(key.encode()).hexdigest()[:24]
 evidence={'file':file,'location':loc,'url':source}
 if cid in contacts:
  if evidence not in contacts[cid]['evidence']:contacts[cid]['evidence'].append(evidence)
  return
 contacts[cid]=dict(id=cid,state='MT',county=county,level='county' if county else 'state',agency=agency,department=department,name=name,title=title,email=email,phone=phone,sourceUrl=source,kind=kind,notes=note,evidence=[evidence])
def rowlinks(row):
 vals=list(row.values());s=' '.join(str(v or '') for v in vals)
 email=next((EMAIL.search(v).group() for v in vals if v and v.startswith('mailto:') and EMAIL.search(v)), '')
 phone=next((clean(v[4:].strip(' ,')) for v in vals if v and v.startswith('tel:')), '')
 if not phone:phone=next(iter(phones(s)),'')
 source=next((v for v in vals if v and v.startswith('http') and 'employee?' in v),'') or next((v for k,v in row.items() if v and v.startswith('http') and 'maps.google' not in v and 'ImageRepository' not in v),'')
 return email,phone,source
root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
for p in sorted(root.glob('*.csv')):
 rows=list(csv.DictReader(p.open(encoding='utf-8-sig'))); count=0
 for i,r in enumerate(rows,2):raw.append({'file':p.name,'location':f'row {i}','data':r})
 if p.name.startswith('fliphtml5'):continue
 prefix=p.stem.split('-2026')[0];county=MAP[prefix]
 for i,r in enumerate(rows,2):
  email,phone,source=rowlinks(r);name=title=department='';kind='person'
  if 'fw-bold' in r:
   name=r['fw-bold'];title=r.get('d-sm-block') or r.get('card-text') or '';department=next((r.get(k.replace(' href',''),'') for k,v in r.items() if v and 'department?' in v),'')
   if not title: title=department or 'Directory entry';kind='department'
  elif 'table' in r:name=r['table'];title=r.get('table (2)','');department=r.get('table (3)','')
  elif 'category-list' in r:department=r['category-list'];name=r.get('col-md-5','');title=department
  elif 'col-md-5' in r:department=r['col-md-5'];title=department;kind='department'
  elif 'mai-accordion-title' in r:
   department=r['mai-accordion-title'];block=r.get('wp-block-paragraph','');ls=[clean(x) for x in block.splitlines() if clean(x)];title=ls[0] if ls else department;name=ls[1].replace('EMAIL','').strip(' –-') if len(ls)>1 else '';kind='person' if name else 'department'
  elif 'has-text-align-center' in r:
   name=r['has-text-align-center'];title=r.get('has-text-align-center (2)','');department=title
  elif 'sixteen' in r:
   for k,v in r.items():
    if v and '|' in v:
     nm,ph=v.split('|',1);add(county,'County government',r['sixteen'],nm,r['sixteen'],'',clean(ph),source,p.name,f'row {i}')
   continue
  elif prefix=='treasurecountymt':continue
  elif prefix=='sgcountymt':
   block=r.get('small-24','')
   for line in block.splitlines():
    em=EMAIL.search(line)
    if em:
     left=line[:em.start()].strip(' –-');parts=re.split(r'[:–]',left,maxsplit=1)
     if len(parts)==2: title,name=parts
     else:name='';title=left
     add(county,'County government',title,name,title,em.group(),'',source,p.name,f'row {i}', 'person' if name else 'department')
   continue
  elif prefix=='libertycountymt':
   department=r.get('wixui-rich-text__text',''); title=department
   for k,v in r.items():
    if v and (v.startswith(('South -','Joplin -','West -'))):add(county,'County government',department,v.split(' - ',1)[1],'Commissioner',email,phone,source,p.name,f'row {i}')
   name=r.get('wixui-rich-text__text (2)','')
  elif prefix=='lincolncountymt':
   for val,nm,ti,em in [('g-block','','Non-Emergency Dispatch',r.get('g-block 3','')),('g-block','Chanel Geer','Administration',r.get('g-block 3','')),('g-block 4','Barb Pfaff','Records',r.get('g-block 10','')),('g-block 6','Brent Shrum','Civil Clerk & Warrants',r.get('g-block 11','')),('g-block 8','Karen Hyslop','Records Technician','')]:
    v=r.get(val,'')
    if (nm and nm in v) or (not nm and r.get('g-block 2')=='Non-Emergency Dispatch'):
     add(county,'County government','Sheriff',nm,ti,em,next(iter(phones(v)),''),'',p.name,f'row {i}','person' if nm else 'department')
   continue
  else:continue
  if name or email or phone:
   add(county,'County government',department,name,title,email,phone,source,p.name,f'row {i}',kind);count+=1
 coverage.append({'file':p.name,'inputRows':len(rows),'parsedRows':count})
# Treasure exports are one vertical contact per file.
for p in root.glob('treasure*.csv'):
 rows=list(csv.reader(p.open()));cells=[r[0] for r in rows[1:] if r]
 add('Treasure','County government','Sheriff',cells[1],cells[0],next(iter(EMAIL.findall(' '.join(cells))),''),next(iter(phones(' '.join(cells))),''),'',p.name,'rows 2-5')
# County legal deskbook: retain leading continuation blocks without guessing their county.
for p in root.glob('fliphtml5*.csv'):
 lines=[r[0] for r in list(csv.reader(p.open()))[1:] if r];county='';role='';block=[]
 roles=['County Attorney','JP/City Judge','Clerk of District Court','Sheriff/Coroner','Clerk & Recorder']
 def flush():
  if county and role and block:
   add(county,'County government',role,block[0],role,next(iter(EMAIL.findall(' '.join(block))),''),next(iter(phones(' '.join(block))),''),'',p.name,'deskbook block',note='2025 Lawyers’ Deskbook snapshot')
 for line in lines+['County Attorney']:
  if line.endswith(' County'):
   flush();county=line[:-7];role='';block=[]
  elif line in roles:flush();role=line;block=[]
  elif role and line not in ['COUNTY OFFICIALS','\uf038'] and not line.startswith('©'):block.append(line)
# Plain-text county entries retain complete source text for review.
for p in root.glob('*.txt'):
 if 'State-of-Montana' in p.name:continue
 text=p.read_text();raw.append({'file':p.name,'location':'document','data':text})
 county=p.stem.replace(' County','')
 if county=='Blaine':
  for i,block in enumerate(text.split('')):
   ls=[clean(x) for x in block.splitlines() if clean(x)];em=EMAIL.search(block)
   if len(ls)>=2 and em:
    title,name=ls[0],ls[1];name=re.split(r'Phone:|\(?406',name)[0].strip();add(county,'County government',title,name,title,em.group(),next(iter(phones(block)),''),'',p.name,f'block {i}')
 else:
  ls=[clean(x) for x in text.splitlines() if clean(x)];dept='';i=0
  while i<len(ls):
   if ls[i]=='Name':dept=ls[i-1];i+=1
   if i+1<len(ls) and ls[i] not in ['Name','Title','Position','Phone','Email'] and not PHONE.search(ls[i]) and not EMAIL.search(ls[i]):
    name,title=ls[i:i+2]
    if title not in ['Name','Title','Position','Phone','Email'] and not PHONE.search(title) and not EMAIL.search(title):
     tail=[];k=i+2
     while k<len(ls) and (PHONE.search(ls[k]) or EMAIL.search(ls[k])):tail.append(ls[k]);k+=1
     if tail or (name.count(' ')>=1 and title not in ['Name','Title']):
      add(county,'County government',dept,name,title,next(iter(EMAIL.findall(' '.join(tail))),''),next(iter(phones(' '.join(tail))),''),'',p.name,f'line {i+1}');i=k;continue
   i+=1
# State PDFs contain ruled tables: extract actual cells, retaining page provenance.
import pdfplumber
SLUG={'Administration':'doa','Agriculture':'agr','Corrections':'cor','Military-Affairs':'mil','Revenue':'rev','Transportation':'tran','Secretary-of-State':'secstate','Auditor':'auditor','Universities':'universities'}
for p in root.glob('*State-of-Montana*.txt'):
 text=p.read_text(); agency=p.stem.split('Directory-')[1].replace('-',' ');slug=next(v for k,v in SLUG.items() if k in p.name);url='https://directory.mt.gov/govt/state-dir/agency/'+slug
 n_before=len(contacts);section=agency;pending=None;headers=[]
 pdf=pdfplumber.open(root.parent/'upload'/p.name.replace('.txt','.pdf'))
 for pn,page in enumerate(pdf.pages,1):
  raw.append({'file':p.name.replace('.txt','.pdf'),'location':f'page {pn}','data':page.extract_text()})
  for table in page.extract_tables():
   if not table or not 2<=len(table[0])<=6:continue
   if any(len(str(c or ''))>650 for row in table for c in row):continue
   first=[clean(c) for c in table[0]]
   hasheader=any('▲' in c or '▼' in c for c in first)
   if hasheader:
    headers=first
    left=table[0][0] or ''
    sec=re.split(r'\n(?:Name|Address)',left)[0]
    if sec and 'Name' not in sec and 'Address' not in sec:section=clean(sec)
    rows=table[1:]
   else:
    rows=table
   if not headers or len(headers)!=len(table[0]):continue
   emailcol=next((i for i,c in enumerate(headers) if 'Email' in c),None)
   phonecol=next((i for i,c in enumerate(headers) if 'Phone' in c or 'Contact Method' in c or 'Main' in c),None)
   for ri,row in enumerate(rows):
    if not row or not row[0] or any('Showing' in (c or '') or 'Search this' in (c or '') for c in row):continue
    original=row[0];joined=clean(original)
    email=clean(row[emailcol]).replace(' ','') if emailcol is not None else ''
    # PDF font substitutes ff/fi ligatures; known substitutions are corrected literally.
    email=email.replace('Shirtli#','Shirtliff').replace('NatheeKaylee.Nathee','Kaylee.Nathee')
    if email and not EMAIL.fullmatch(email):email=''
    phone=next(iter(phones(row[phonecol] or '')),'') if phonecol is not None else ''
    if not email and not phone:continue
    if re.search(r'Fax|FAX|TTY',joined):continue
    if 'Universities' in p.name:
     org=[]
     for line in original.splitlines():
      if re.search(r'\d|, MT|Montana \d',line):break
      org.append(line)
     name='';title=clean(' '.join(org));kind='organization';dep=title
    elif 'Auditor' in p.name and ',' in joined:
     name,title=map(clean,joined.split(',',1));kind='person';dep=section
    else:
     name,title,kind=split_person(joined);dep=section
     ls=[clean(x) for x in original.splitlines() if clean(x)]
     if not name and len(ls)>1 and email:
      if 'Secretary-of-State' in p.name:name=ls[0];title=clean(' '.join(ls[1:]));kind='person'
      elif len(ls[-1].split())>=2:name=ls[-1];title=clean(' '.join(ls[:-1]));kind='person'
     if not name and email and 'Corrections' in p.name:
      m=re.match(r'(.*(?:Chief|Assistant|Officer|Warden)) (.+)',joined)
      if m:title,name=m.groups();kind='person'
    note='Imported PDF snapshot'
    if kind!='organization' and re.search(r'PO Box|MT \d|HDelier|Phone:|Fax:|\d{5}',joined):
     # Overprinted address blocks cannot safely be presented as staff identities.
     note+='; overlapping print text requires review';kind='review';name='';title=dep+' — source row requires review'
    add('',agency,dep,name,title,email,phone,url,p.name.replace('.txt','.pdf'),f'page {pn}, table row {ri+1}',kind,note)
 coverage.append({'file':p.name.replace('.txt','.pdf'),'pages':len(pdf.pages),'contacts':len(contacts)-n_before,'emailOccurrences':text.count('@')})
# University print tables lack borders on most pages; recover named institutions from layout text.
for p in root.glob('*Universities-Colleges.txt'):
 text=p.read_text().replace('\f','\n')
 for segment in text.split('Showing all entries'):
  if 'Address' not in segment or 'Main' not in segment:continue
  lines=segment.splitlines();start=next((i for i,l in enumerate(lines) if re.search(r'406-\d{3}-\d{4}',l)),None)
  if start is None:continue
  org=[];phone=next(iter(phones(lines[start])), '')
  for line in lines[start:]:
   left=re.split(r'\s{2,}',line.strip())[0] if line.strip() else ''
   if not left:continue
   if re.search(r'\d|, MT|Butte MT|Google|experience|Analytics|the site|Accept|Reject',left):break
   org.append(left)
  name=clean(' '.join(org))
  if name:add('',agency='Universities Colleges',department=name,name='',title=name,email='',phone=phone,source='https://directory.mt.gov/govt/state-dir/agency/',file=p.name.replace('.txt','.pdf'),loc='institution listing',kind='organization')
(out/'contacts.json').write_text(json.dumps(list(contacts.values()),ensure_ascii=False,indent=2))
(out/'raw-sources.json').write_text(json.dumps(raw,ensure_ascii=False))
(out/'coverage.json').write_text(json.dumps(coverage,indent=2))
print(json.dumps({'contacts':len(contacts),'county':sum(c['level']=='county' for c in contacts.values()),'state':sum(c['level']=='state' for c in contacts.values()),'coverage':coverage},indent=2))
