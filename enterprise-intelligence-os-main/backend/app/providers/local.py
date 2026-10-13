class LocalDemoProvider:
 name='local-demo'; simulated=True
 def complete(self,prompt:str)->str: return 'Deterministic local provider: no external model was called.'
