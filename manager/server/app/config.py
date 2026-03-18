'''
    0: local
    1: production
'''

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv('MODE'))