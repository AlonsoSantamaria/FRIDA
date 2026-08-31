from datetime import date
import sys
from frida.persistence import StagingStore
from frida.strategic_briefing import StrategicBriefingService
s=StagingStore('data/frida-final-london-appraisal.sqlite3'); x=StrategicBriefingService(s)
try:
 cutoffs=(date(2006,11,24),date(2021,4,15)) if len(sys.argv)==1 else (date.fromisoformat(sys.argv[1]),)
 for cutoff in cutoffs:
  identifier,_,brief,meta=x.create_historical(cutoff)
  print({'brief_id':identifier,'cutoff':cutoff.isoformat(),'posture':brief['executive_posture'],'meta':meta})
finally: x.close();s.close()
