"""Faz o Python usar o repositório de certificados do Windows em vez do seu
próprio bundle (certifi). Necessário porque antivírus com inspeção de HTTPS
(ex.: Norton 360) re-assinam certificados com uma CA própria que o Windows
já confia, mas o bundle padrão do Python não. Sem isso, qualquer chamada
HTTPS (Google, Anthropic, Adzuna) falha com CERTIFICATE_VERIFY_FAILED.

Importe este módulo antes de qualquer outro que faça chamadas de rede.
"""
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass
