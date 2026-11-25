from pathlib import Path
from pypdf import PdfReader
from zipfile import ZipFile
import re,xml.etree.ElementTree as E
d=Path(r'D:\Desktop\汇报')
for f in d.rglob('*.pdf'):
 if not any(x in f.name.lower() for x in ['sciadv','super-resolution','fourier','neuromorphic','multi-imaging','多波长','01968']): continue
 try:
  r=PdfReader(f); print(f.name,len(r.pages))
  for i,p in enumerate(r.pages):
   s=p.extract_text() or ''
   for m in re.finditer(r'(?im)^\s*(?:fig(?:ure)?\.?\s*\d+[.:])[^\n]{8,160}',s): print(i+1,m.group().strip())
 except Exception as e: print(e)
for f in d.rglob('*.pptx'):
 if not any(t in str(f) for t in ['10.29','10.3','12号','4.16']):continue
 print('\n',f)
 with ZipFile(f) as z:
  for n in sorted(z.namelist()):
   if re.fullmatch(r'ppt/slides/slide\d+.xml',n):
    vals=[t.text for t in E.fromstring(z.read(n)).iter() if t.tag.endswith('}t') and t.text]
    if vals: print(n.split('/')[-1],' '.join(vals)[:450])
