from pydantic import BaseModel
from typing import Dict

class SLARules(BaseModel):
    zones: Dict[str, int]
    priorities: Dict[str, int]
