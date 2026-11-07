# Notas ficticias para probar el módulo SOAP

Estas cinco notas son inventadas. No corresponden a ninguna persona real y no deben usarse como fuente clínica.

- `nota_depresion.txt`
- `nota_esquizofrenia.txt`
- `nota_bipolar.txt`
- `nota_ansiedad.txt`
- `nota_tdah.txt`

Van en `pruebas/`, **no en `datos/`**, para que el RAG no las cite como bibliografía. Cada una declara que es ficticia y omite datos a propósito (por ejemplo, el peso o la litemia) para comprobar que el modelo escribe “no consta” en lugar de inventar.

La estructura SOAP se prueba con `python probar_soap.py` y las funciones puras con `python -m pytest test_soap.py`.
