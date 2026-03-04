# Agents package
# Each agent is responsible for one step in the pipeline

from .email_agent import fetch_newsletters
from .filter_agent import filter_newsletters
from .content_agent import analyze_all_newsletters