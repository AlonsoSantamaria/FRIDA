from pathlib import Path
from frida.persistence import StagingStore
from frida.strategic_briefing import StrategicBriefingService

path=Path('data/frida-final-london-appraisal.sqlite3')
store=StagingStore(str(path))
service=StrategicBriefingService(store)
try:
    brief_id, foresight, brief, meta=service.create_current()
    print({'brief_id':brief_id,'posture':brief['executive_posture'],'agents':['Advisory Foresight','Executive Briefing'],'foresight':foresight,'brief':brief,'meta':meta})
finally:
    service.close(); store.close()
