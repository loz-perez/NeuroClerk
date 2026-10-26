# Documentos para la carpeta `datos`

*Actualizado el 26 de octubre de 2026.*

Para que NeuroClerk responda mejor no hacen falta más documentos, sino los correctos: fuentes oficiales, actuales, con texto seleccionable y sin contradicciones entre sí. Lo primero son las fichas técnicas de los psicofármacos más usados, que es lo que más mejora las respuestas con menos esfuerzo.

> Los documentos de `datos/` **no se suben al repositorio** (está en el `.gitignore`), por su tamaño y por derechos de autor. Cada persona descarga los suyos de las fuentes indicadas abajo.

## Fichas técnicas de psicofármacos

Son la fuente más confiable para indicaciones, dosis, interacciones y advertencias, y se descargan gratis de [CIMA (AEMPS)](https://cima.aemps.es). Las marcadas con ✅ son las que se usan en las pruebas del proyecto.

| Grupo | Fármacos sugeridos |
| --- | --- |
| Antidepresivos ISRS | fluoxetina, sertralina ✅, paroxetina, citalopram, escitalopram, fluvoxamina |
| Otros antidepresivos | venlafaxina, duloxetina, mirtazapina, bupropión, trazodona, vortioxetina, agomelatina |
| Tricíclicos e IMAO | amitriptilina, clomipramina, moclobemida |
| Antipsicóticos | haloperidol, risperidona, paliperidona, olanzapina, quetiapina ✅, aripiprazol, clozapina ✅, ziprasidona, amisulprida, lurasidona, cariprazina |
| Estabilizadores del ánimo | litio ✅, valproato, carbamazepina, oxcarbazepina, lamotrigina |
| Ansiolíticos e hipnóticos | alprazolam, lorazepam, clonazepam, diazepam, zolpidem |
| TDAH | metilfenidato, atomoxetina, lisdexanfetamina |
| Adicciones | naltrexona, disulfiram, buprenorfina, metadona |
| No psiquiátricos que interaccionan a menudo | tramadol, warfarina, IECA (enalapril), AINE (ibuprofeno), claritromicina, linezolid, ciprofloxacino |

La última fila sirve para que el sistema encuentre la interacción desde los dos lados.

Para el contexto de Uruguay, conviene sumar el **Formulario Terapéutico de Medicamentos del MSP**, que indica qué está disponible en el país. Las fichas de CIMA son de España y pueden incluir presentaciones o marcas que no se venden en Uruguay.

Nombra los archivos de forma clara (`FT_Litio.pdf`, no `FT_63845.pdf`), porque el modelo cita el nombre del archivo.

## Interacciones y criterios diagnósticos

| Documento | Para qué sirve | Estado |
| --- | --- | --- |
| *Introducción a las interacciones farmacológicas* (SEFH) | Mecanismos de interacción y tablas de fármacos de riesgo | ✅ En uso; sus tablas funcionan bien |
| Tabla de enzimas CYP450 (*Flockhart Table*, Universidad de Indiana) | Referencia clásica de sustratos, inhibidores e inductores | Pendiente; revisar sus condiciones de uso |
| DSM-5 | Criterios diagnósticos | ✅ En uso; el DSM-5-TR (2022) es más actual. Ninguno se puede compartir |
| CIE-11 (OMS), guía clínica CDDR | Criterios diagnósticos oficiales y gratuitos, en PDF | Pendiente; comprobar si hay versión en español |

Si la CIE-11 solo está en inglés, igual sirve: `multilingual-e5-base` funciona bien con documentos en inglés.

## Guías clínicas y escalas

Las guías responden preguntas de "qué hacer", no solo de "qué es". Las escalas sirven para el futuro módulo de notas clínicas.

| Documento | Contenido | Idioma | Licencia |
| --- | --- | --- | --- |
| GuíaSalud (España) | Depresión en el adulto, esquizofrenia, trastorno bipolar, ansiedad, TDAH, insomnio | Español | Gratuitas |
| Guía mhGAP (OMS/OPS) | Salud mental en atención primaria | Español | Gratuita |
| NICE (Reino Unido) | Guías completas; útiles sobre todo para seguimiento, como los controles del litio | Inglés | Gratuitas |
| PHQ-9 y GAD-7 | Escalas de depresión y ansiedad | Español disponible | Uso libre, sin permiso |
| YMRS y PANSS | Escalas de manía y de síntomas psicóticos | — | Verificar antes de usar; la PANSS tiene derechos de autor y se usa con licencia |

## Qué no poner en `datos`

`datos` es la fuente de verdad del sistema: todo lo que esté ahí puede terminar citado como bibliografía.

- **Notas clínicas y casos ficticios.** El modelo podría citarlos como si fueran una fuente. Van en otra carpeta, por ejemplo `pruebas/`.
- **Datos de pacientes reales**, ni siquiera anonimizados, mientras sea un proyecto en desarrollo.
- **Dos versiones del mismo documento**, como una ficha vieja y una nueva del mismo fármaco: si se contradicen, el modelo puede citar cualquiera de las dos.
- **Artículos sueltos de internet, blogs o Wikipedia.** Bajan la calidad de las fuentes.
- **PDFs escaneados sin texto o imágenes.** `rag.py` no los puede leer hasta que se agregue OCR.

## Para que escale bien

1. **Llevar un registro de fuentes.** Un archivo `fuentes.csv`, fuera de `datos`, con el nombre, la fuente, la URL y la fecha de descarga de cada documento. Las fichas técnicas se actualizan, y así se sabe cuándo renovarlas.
2. **Con muchas fichas, buscar por tipo de documento.** Hoy `rag.py` busca 3 candidatos por archivo; con 50 fichas son 150 candidatos por pregunta, más lento y con más ruido. Conviene buscar por tipo (ficha, guía, diagnóstico) usando los metadatos de ChromaDB.
3. **Volver a correr `probar_tablas.py` después de cada tanda de documentos nuevos**, para confirmar que la búsqueda sigue funcionando bien.
