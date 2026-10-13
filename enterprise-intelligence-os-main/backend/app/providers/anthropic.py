import os
from .base import ProviderNotConfiguredError
class AnthropicProvider:
 def __init__(self):
  if not os.getenv('ANTHROPIC_API_KEY'): raise ProviderNotConfiguredError('ANTHROPIC_API_KEY is not configured')
