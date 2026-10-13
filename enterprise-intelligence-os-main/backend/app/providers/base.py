from typing import Protocol
class Provider(Protocol):
 def complete(self, prompt:str)->str: ...
class ProviderNotConfiguredError(RuntimeError): pass
