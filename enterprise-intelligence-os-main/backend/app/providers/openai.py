import os
from .base import ProviderNotConfiguredError
class OpenAIProvider:
 def __init__(self):
  if not os.getenv('OPENAI_API_KEY'): raise ProviderNotConfiguredError('OPENAI_API_KEY is not configured')
